from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import asyncio


class Navigator:
    def __init__(self, method, show_visuals, logger, verbose):
        self.method = method
        self.show_visuals = show_visuals
        self.playwright_instance = None
        self.browser = None
        self.context = None
        self.page = None
        self.logger = logger
        self.verbose = verbose

    async def detect_elements(self):
        if self.method == 'ocr':
            return await self._detect_elements_ocr()
        else:
            return await self._detect_elements_xpath()

    async def _detect_elements_xpath(self):
        labels = await self.page.query_selector_all('label')
        inputs = await self.page.query_selector_all('input, select, textarea, button, a')

        label_map = {}
        for label in labels:
            for_attr = await label.get_attribute('for')
            text = await label.inner_text()
            if for_attr:
                label_map[for_attr] = text
            else:
                label_id = await label.evaluate('el => el.id')
                if label_id:
                    label_map[label_id] = text

        elements = await self.page.query_selector_all('a, button, [role="button"], input, textarea, select')
        return [
            {
                'element': elem,
                'bbox': await elem.bounding_box(),
                'tag': await elem.evaluate('el => el.tagName.toLowerCase()'),
                'type': await elem.evaluate('el => el.type'),
                'placeholder': await elem.get_attribute('placeholder'),
                'aria_label': await elem.get_attribute('aria-label'),
                'inner_text': await elem.inner_text(),
                'id': await elem.get_attribute('id'),
                'description': label_map.get(await elem.get_attribute('id')) or await elem.inner_text() or await elem.get_attribute('aria-label') or await elem.get_attribute('placeholder') or 'No description'
            }
            for elem in elements if await elem.is_visible()
        ]

    async def _add_visual_marker(self, number, bbox, element_type):
        color = 'red' if element_type == 'input' else 'yellow'
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

    async def map_elements(self, elements):
        mapped = {}
        for i, element in enumerate(elements, 1):
            mapped_type = 'input' if element['tag'] in ['input', 'textarea', 'select'] or (element['tag'] == 'input' and element['type'] in ['text', 'search', 'email', 'password', 'number']) else 'clickable'

            description = element['description'].strip()

            # Skip elements with no description
            if description == 'No description':
                continue

            mapped[len(mapped) + 1] = {
                'element': element['element'],
                'bbox': element['bbox'],
                'type': mapped_type,
                'description': description
            }

            if self.show_visuals:
                await self._add_visual_marker(len(mapped), element['bbox'], mapped_type)

        return mapped

    async def setup_browser(self):
        if not self.playwright_instance:
            self.playwright_instance = await async_playwright().start()
            self.browser = await self.playwright_instance.chromium.launch(headless=False)
            self.context = await self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                viewport={'width': 1280, 'height': 720}
            )
            self.page = await self.context.new_page()
        return self.browser.is_connected()

    async def navigate_to(self, url, max_retries=3):
        browser_connected = await self.setup_browser()
        if not browser_connected:
            print("Failed to connect to the browser. Please check your setup.")
            return None

        for attempt in range(max_retries):
            try:
                print(f"Navigating to {url}")
                response = await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)

                if response.status >= 400:
                    print(f"Received HTTP status {response.status}. Retrying...")
                    continue

                print("Page loaded successfully. Mapping elements...")
                elements = await self.detect_elements()
                mapped_elements = await self.map_elements(elements)

                return mapped_elements, self.page.url

            except Exception as e:
                print(f"An error occurred while navigating to {url}: {e}")

        print("Failed to navigate to the page after maximum retries.")
        return None

    async def perform_action(self, action, mapped_elements):
        try:
            if "element" not in action or action["element"] not in mapped_elements:
                self.logger.error(f"Element {action.get('element')} not found on the page.")
                return False

            element_info = mapped_elements[action["element"]]
            self.logger.info(f"Attempting to perform {action['type']} on element {action['element']} ({element_info['description']})")

            if action["type"] == "click":
                await element_info['element'].click()
            elif action["type"] in ["input", "input_enter"]:
                await element_info["element"].fill(action["text"])
                if action["type"] == "input_enter":
                    await self.page.keyboard.press("Enter")
            else:
                self.logger.error(f"Unknown action type: {action['type']}")
                return False

            await asyncio.sleep(2)  # Wait for 2 seconds after each action

            try:
                await self.page.wait_for_load_state("networkidle", timeout=30000)
                self.logger.info("Page loaded after action.")
            except PlaywrightTimeoutError:
                self.logger.warning("Page load timed out after action. Continuing...")

            self.logger.info(f"Successfully performed action: {action['type']} on element {action['element']}")
            return True

        except Exception as e:
            self.logger.error(f"Error performing action: {str(e)}")
            return False

    async def cleanup(self):
        if self.browser:
            self.logger.info("Closing browser.")
            await self.browser.close()
        if self.playwright_instance:
            await self.playwright_instance.stop()