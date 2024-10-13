import asyncio

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError, async_playwright

from plugin_manager import PluginManager
from utils import get_logger


class Navigator:
    def __init__(self, method: str, show_visuals: bool, verbose: bool) -> None:
        self.logger = get_logger()
        self.method = method
        self.show_visuals = show_visuals
        self.playwright_instance = None
        self.browser = None
        self.context = None
        self.page: Page | None = None
        self.verbose = verbose

    async def detect_elements(self) -> list[dict]:
        if self.method == "ocr":
            return await self._detect_elements_ocr()
        return await self._detect_elements_xpath()

    async def _detect_elements_xpath(self) -> list[dict]:
        if not self.page:
            msg = "Page is not initialized"
            raise ValueError(msg)

        labels, inputs = await asyncio.gather(
            self.page.query_selector_all("label"), self.page.query_selector_all("input, select, textarea, button, a"),
        )

        label_map = {}
        for label in labels:
            for_attr, text = await asyncio.gather(label.get_attribute("for"), label.inner_text())
            if for_attr:
                label_map[for_attr] = text
            else:
                label_id = await label.evaluate("el => el.id")
                if label_id:
                    label_map[label_id] = text

        elements = await self.page.query_selector_all('a, button, [role="button"], input, textarea, select')
        return [
            {
                "element": elem,
                "bbox": await elem.bounding_box(),
                "tag": await elem.evaluate("el => el.tagName.toLowerCase()"),
                "type": await elem.evaluate("el => el.type"),
                "placeholder": await elem.get_attribute("placeholder"),
                "aria_label": await elem.get_attribute("aria-label"),
                "inner_text": await elem.inner_text(),
                "id": await elem.get_attribute("id"),
                "description": (
                    label_map.get(await elem.get_attribute("id"))
                    or await elem.inner_text()
                    or await elem.get_attribute("aria-label")
                    or await elem.get_attribute("placeholder")
                    or "No description"
                ),
                "is_dropdown": await elem.evaluate('el => el.tagName.toLowerCase() === "select"'),
            }
            for elem in elements
            if await elem.is_visible()
        ]

    async def _add_visual_marker(self, number: int, bbox: dict[str, float], element_type: str) -> None:
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

    async def map_elements(self, elements: list[dict]) -> dict[int, dict]:
        mapped = {}
        for element in elements:
            mapped_type = (
                "dropdown"
                if element["is_dropdown"]
                else (
                    "input"
                    if element["tag"] in ["input", "textarea"] and element["type"] not in ["submit", "button", "reset"]
                    else "clickable"
                )
            )

            description = element["description"].strip()

            if description == "No description":
                continue

            mapped[len(mapped) + 1] = {
                "element": element["element"],
                "bbox": element["bbox"],
                "type": mapped_type,
                "description": description,
            }

            if self.show_visuals:
                await self._add_visual_marker(len(mapped), element["bbox"], mapped_type)

        return mapped

    async def setup_browser(self) -> bool:
        if not self.playwright_instance:
            self.playwright_instance = await async_playwright().start()
            self.browser = await self.playwright_instance.chromium.launch(headless=False)
            self.context = await self.browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 720},
            )
            self.page = await self.context.new_page()
        return self.browser.is_connected()

    async def navigate_to(self, url: str, max_retries: int = 3) -> tuple[dict[int, dict], str] | None:
        if not await self.setup_browser():
            self.logger.error("Failed to connect to the browser. Please check your setup.")
            return None

        attempt = 0
        while attempt < max_retries:
            attempt += 1
            self.logger.info(f"Attempt {attempt}/{max_retries}: Navigating to {url}")

            try:
                response = await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)

                if response.status >= 400:
                    self.logger.warning(f"Received HTTP status {response.status}. Retrying...")
                    continue

                self.logger.info("Page loaded successfully. Mapping elements...")
                elements = await self.detect_elements()
                mapped_elements = await self.map_elements(elements)
                return mapped_elements, self.page.url

            except Exception as e:
                self.logger.exception(f"Attempt {attempt}/{max_retries} failed: {e!s}")

        self.logger.error(f"Failed to navigate to {url} after {max_retries} attempts.")
        return None

    async def perform_action(
        self, action: dict, mapped_elements: dict[int, dict], plugin_manager: PluginManager,
    ) -> bool:
        try:
            if "element" not in action or action["element"] not in mapped_elements:
                self.logger.error(f"Element {action.get('element')} not found on the page.")
                return False

            element_info = mapped_elements[action["element"]]
            self.logger.info(
                f"Attempting to perform {action['type']} on element {action['element']} ({element_info['description']})",
            )

            # Plugin pre-action pipeline
            for plugin in plugin_manager.get_plugins():
                action = await plugin.pre_action(action, mapped_elements)

            if action["type"] == "click":
                await element_info["element"].click()
            elif action["type"] == "input":
                await element_info["element"].fill(action["text"])
            elif action["type"] == "select":
                if element_info["type"] == "dropdown":
                    await element_info["element"].select_option(value=action["value"])
                else:
                    self.logger.error(
                        f"Cannot perform select action on non-dropdown element: {element_info['description']}",
                    )
                    return False
            else:
                self.logger.error(f"Unknown action type: {action['type']}")
                return False

            await asyncio.sleep(2)

            try:
                await self.page.wait_for_load_state("networkidle", timeout=30000)
                self.logger.info("Page loaded after action.")
            except PlaywrightTimeoutError:
                self.logger.warning("Page load timed out after action. Continuing...")

            # Plugin post-action pipeline
            for plugin in plugin_manager.get_plugins():
                await plugin.post_action(action, True)

            self.logger.info(f"Successfully performed action: {action['type']} on element {action['element']}")
            return True

        except Exception as e:
            self.logger.exception(f"Error performing action: {e!s}")

            # Plugin error handling
            for plugin in plugin_manager.get_plugins():
                await plugin.on_error(e)

            return False

    async def cleanup(self) -> None:
        if self.browser:
            self.logger.info("Closing browser.")
            await self.browser.close()
        if self.playwright_instance:
            await self.playwright_instance.stop()

    async def _detect_elements_ocr(self) -> list[dict]:
        # Placeholder for OCR implementation
        return []
