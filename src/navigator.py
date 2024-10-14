import asyncio
from typing import Any

from playwright.async_api import Page, async_playwright

from plugins.plugin_manager import PluginManager
from utils import get_logger


HTTP_ERROR_STATUS = 400

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
            self.page.query_selector_all("label"),
            self.page.query_selector_all("input, select, textarea, button, a"),
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

    async def navigate_to(
        self, url: str, plugin_manager: PluginManager, max_retries: int = 3,
    ) -> dict[int, dict[str, Any]] | str | None:
        result = await self._navigate_to_impl(url, max_retries)
        if result:
            mapped_elements, current_url = result
            await plugin_manager.handle_event("navigation", {"url": current_url, "elements": mapped_elements})
        return result

    async def _navigate_to_impl(self, url: str, max_retries: int = 3) -> dict[int, dict[str, Any]] | str | None:
        if not await self.setup_browser():
            self.logger.error("Failed to connect to the browser. Please check your setup.")
            return None

        attempt = 0
        while attempt < max_retries:
            attempt += 1
            self.logger.info("Attempt %s/%s: Navigating to %s", attempt, max_retries, url)

            try:
                response = await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)

                if response.status >= HTTP_ERROR_STATUS:
                    self.logger.warning("Received HTTP status %s. Retrying...", response.status)
                    continue

                self.logger.info("Page loaded successfully. Mapping elements...")
                elements = await self.detect_elements()
                mapped_elements = await self.map_elements(elements)

                return mapped_elements, self.page.url

            except Exception:
                self.logger.exception("Attempt %s/%s failed", attempt, max_retries)

        self.logger.error("Failed to navigate to %s after %s attempts.", url, max_retries)
        return None

    async def perform_action(
        self, action: dict[str, Any], mapped_elements: dict[int, dict[str, Any]], plugin_manager: PluginManager,
    ) -> bool:
        try:
            # Pre-action hook
            plugin_action = await plugin_manager.pre_decision(
                {"action": action, "elements": mapped_elements, "url": self.page.url},
            )
            if plugin_action:
                action.update(plugin_action)

            if "type" not in action:
                self.logger.error("Invalid action: 'type' key is missing. Action: %s", action)
                return False

            if action["type"] == "submit":
                await self.page.keyboard.press("Enter")
                await asyncio.sleep(2)
                success = True
            elif "element" in action and action["element"] in mapped_elements:
                element_info = mapped_elements[action["element"]]
                self.logger.info(
                    "Attempting to perform %s on element %s (%s)",
                    action["type"],
                    action["element"],
                    element_info["description"],
                )

                if action["type"] == "click":
                    await element_info["element"].click()
                    success = True
                elif action["type"] == "input":
                    await element_info["element"].fill(action["text"])
                    success = True
                else:
                    self.logger.error("Unknown action type: %s", action["type"])
                    success = False
            else:
                self.logger.error("Element %s not found on the page.", action.get("element"))
                success = False

            # Post-action hook
            await plugin_manager.post_decision({"action": action, "success": success}, {"elements": mapped_elements})
            return success

        except Exception:
            self.logger.exception("Error performing action")
            # Error handling hook
            await plugin_manager.handle_event("error", {"error": "Action execution failed", "action": action})
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
