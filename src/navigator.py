import asyncio
from typing import Any, NotRequired, TypedDict

from playwright.async_api import Browser, BrowserContext, ElementHandle, Page, async_playwright

from plugins.plugin_manager import PluginManager
from utils import get_logger


class NavigatorException(Exception):
    """Base exception for Navigator class."""


class ElementNotFoundException(NavigatorException):
    """Raised when an element is not found on the page."""


class ElementInfo(TypedDict):
    element: ElementHandle
    bbox: dict[str, float]
    type: str
    description: str


class ActionDict(TypedDict):
    type: str
    element: NotRequired[int]
    text: NotRequired[str]


class Navigator:
    def __init__(
        self,
        headless: bool = False,
        user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        viewport: dict[str, int] = {"width": 1280, "height": 720},
        max_retries: int = 3,
        page_load_timeout: int = 60000,
        detection_method: str = "xpath",
        show_visuals: bool = False,
    ) -> None:
        self.logger = get_logger()
        self.headless = headless
        self.user_agent = user_agent
        self.viewport = viewport
        self.max_retries = max_retries
        self.page_load_timeout = page_load_timeout
        self.detection_method = detection_method
        self.show_visuals = show_visuals
        self.playwright_instance = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    async def __aenter__(self):
        if not self.page:
            await self.setup_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    async def setup_browser(self) -> None:
        """Initialize the browser, context, and page."""
        if not self.playwright_instance:
            self.playwright_instance = await async_playwright().start()
            self.browser = await self.playwright_instance.chromium.launch(headless=self.headless)
            self.context = await self.browser.new_context(
                user_agent=self.user_agent,
                viewport=self.viewport,
            )
            self.page = await self.context.new_page()

    async def cleanup(self) -> None:
        """Clean up browser resources."""
        if self.browser:
            self.logger.info("Closing browser.")
            await self.browser.close()
        if self.playwright_instance:
            await self.playwright_instance.stop()

    async def navigate_to(self, url: str, plugin_manager: PluginManager) -> tuple[dict[int, ElementInfo], str]:
        """Navigate to a URL and return mapped elements and current URL."""
        if not self.page:
            await self.setup_browser()  # Ensure the browser is set up
            if not self.page:
                msg = "Failed to initialize page"
                raise NavigatorException(msg)

        for attempt in range(1, self.max_retries + 1):
            try:
                self.logger.info("Attempt %s/%s: Navigating to %s", attempt, self.max_retries, url)
                response = await self.page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=self.page_load_timeout,
                )

                if response.status >= 400:
                    self.logger.warning("Received HTTP status %s. Retrying...", response.status)
                    continue

                self.logger.info("Page loaded successfully. Mapping elements...")
                elements = await self._detect_elements()
                mapped_elements = await self._map_elements(elements)

                await plugin_manager.handle_event("navigation", {"url": self.page.url, "elements": mapped_elements})
                return mapped_elements, self.page.url

            except Exception as e:
                self.logger.exception("Navigation attempt %s/%s failed: %s", attempt, self.max_retries, str(e))

        msg = f"Failed to navigate to {url} after {self.max_retries} attempts."
        raise NavigatorException(msg)

    async def _detect_elements(self) -> list[dict[str, Any]]:
        """Detect elements on the page using the configured method."""
        if self.detection_method == "ocr":
            return await self._detect_elements_ocr()
        return await self._detect_elements_xpath()

    async def _detect_elements_xpath(self) -> list[dict[str, Any]]:
        """Detect elements using XPath."""
        if not self.page:
            msg = "Page is not initialized"
            raise NavigatorException(msg)

        labels, inputs = await asyncio.gather(
            self.page.query_selector_all("label"),
            self.page.query_selector_all("input, select, textarea, button, a"),
        )

        label_map = await self._create_label_map(labels)
        elements = await self.page.query_selector_all('a, button, [role="button"], input, textarea, select')

        return [await self._create_element_info(elem, label_map) for elem in elements if await elem.is_visible()]

    async def _create_label_map(self, labels: list[ElementHandle]) -> dict[str, str]:
        """Create a mapping of element IDs to their labels."""
        label_map = {}
        for label in labels:
            for_attr, text = await asyncio.gather(label.get_attribute("for"), label.inner_text())
            if for_attr:
                label_map[for_attr] = text
            else:
                label_id = await label.evaluate("el => el.id")
                if label_id:
                    label_map[label_id] = text
        return label_map

    async def _create_element_info(self, elem: ElementHandle, label_map: dict[str, str]) -> dict[str, Any]:
        """Create a dictionary of element information."""
        elem_id = await elem.get_attribute("id")
        return {
            "element": elem,
            "bbox": await elem.bounding_box(),
            "tag": await elem.evaluate("el => el.tagName.toLowerCase()"),
            "type": await elem.evaluate("el => el.type"),
            "placeholder": await elem.get_attribute("placeholder"),
            "aria_label": await elem.get_attribute("aria-label"),
            "inner_text": await elem.inner_text(),
            "id": elem_id,
            "description": label_map.get(elem_id)
            or await elem.inner_text()
            or await elem.get_attribute("aria-label")
            or await elem.get_attribute("placeholder")
            or "No description",
            "is_dropdown": await elem.evaluate('el => el.tagName.toLowerCase() === "select"'),
        }

    async def _map_elements(self, elements: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
        """Map detected elements to a numbered dictionary."""
        mapped = {}
        for idx, element in enumerate(elements, start=1):
            if element["description"].strip() == "No description":
                continue

            mapped_type = self._determine_element_type(element)
            mapped[idx] = {
                "element": element["element"],
                "bbox": element["bbox"],
                "type": mapped_type,
                "description": element["description"].strip(),
            }

            if self.show_visuals:
                await self._add_visual_marker(idx, element["bbox"], mapped_type)

        return mapped

    @staticmethod
    def _determine_element_type(element: dict[str, Any]) -> str:
        """Determine the type of an element."""
        if element["is_dropdown"]:
            return "dropdown"
        if element["tag"] in ["input", "textarea"] and element["type"] not in ["submit", "button", "reset"]:
            return "input"
        return "clickable"

    async def _add_visual_marker(self, number: int, bbox: dict[str, float], element_type: str) -> None:
        """Add a visual marker to an element on the page."""
        if not self.page:
            return

        color = "red" if element_type == "input" else "yellow"
        await self.page.evaluate(f"""() => {{
            const div = document.createElement('div');
            div.textContent = '{number}';
            div.style.position = 'absolute';
            div.style.left = '{bbox['x']}px';
            div.style.top = '{bbox['y']}px';
            div.style.backgroundColor = '{color}';
            div.style.color = 'black';
            div.style.padding = '2px';
            div.style.border = '1px solid black';
            div.style.zIndex = '9999';
            document.body.appendChild(div);
        }}""")

    async def perform_action(
        self,
        action: dict[str, Any],
        mapped_elements: dict[int, dict[str, Any]],
        plugin_manager: PluginManager,
    ) -> bool:
        """Perform an action on the page."""
        try:
            plugin_action = await plugin_manager.pre_decision(
                {"action": action, "elements": mapped_elements, "url": self.page.url},
            )
            if plugin_action:
                action.update(plugin_action)

            if "type" not in action:
                msg = f"Invalid action: 'type' key is missing. Action: {action}"
                raise NavigatorException(msg)

            success = await self._execute_action(action, mapped_elements)

            await plugin_manager.post_decision({"action": action, "success": success}, {"elements": mapped_elements})
            return success

        except Exception as e:
            self.logger.exception("Error performing action: %s", str(e))
            await plugin_manager.handle_event("error", {"error": "Action execution failed", "action": action})
            return False

    async def _execute_action(self, action: ActionDict, mapped_elements: dict[int, ElementInfo]) -> bool:
        """Execute a specific action."""
        match action["type"]:
            case "submit":
                await self.page.keyboard.press("Enter")
                await asyncio.sleep(2)
                return True
            case "click":
                if "element" not in action or action["element"] not in mapped_elements:
                    msg = f"Element {action.get('element')} not found on the page."
                    raise ElementNotFoundException(msg)

                element_info = mapped_elements[action["element"]]
                self.logger.info(
                    "Clicking element %s (%s)",
                    action["element"],
                    element_info["description"],
                )
                await element_info["element"].click()
                return True
            case "input":
                if "element" not in action or action["element"] not in mapped_elements:
                    msg = f"Element {action.get('element')} not found on the page."
                    raise ElementNotFoundException(msg)

                element_info = mapped_elements[action["element"]]
                self.logger.info(
                    "Inputting text into element %s (%s)",
                    action["element"],
                    element_info["description"],
                )
                return await self._safe_fill(element_info["element"], action["text"])
            case _:
                msg = f"Unknown action type: {action['type']}"
                raise NavigatorException(msg)

    async def _safe_fill(self, element: ElementHandle, text: str) -> bool:
        """Safely fill an input element with text."""
        if await self._is_input_element(element):
            await element.fill(text)
            return True
        self.logger.error("Element is not an input: %s", await element.evaluate("el => el.outerHTML"))
        return False

    @staticmethod
    async def _is_input_element(element: ElementHandle) -> bool:
        """Check if an element is an input element."""
        tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
        is_contenteditable = await element.evaluate("el => el.getAttribute('contenteditable') === 'true'")
        return tag_name in ["input", "textarea"] or is_contenteditable

    async def _detect_elements_ocr(self) -> list[dict[str, Any]]:
        """Detect elements using OCR (placeholder)."""
        # Implement OCR logic here
        return []
