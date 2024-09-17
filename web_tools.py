from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

class WebTools:
    def __init__(self, method, show_visuals):
        self.method = method
        self.show_visuals = show_visuals
        self.playwright_instance = None
        self.browser = None
        self.context = None
        self.page = None

    async def detect_elements(self, method='xpath'):
        if method == 'ocr':
            return await self._detect_elements_ocr()
        else:
            return await self._detect_elements_xpath()

    async def _detect_elements_xpath(self):
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
                'id': await elem.get_attribute('id')
            }
            for elem in elements if await elem.is_visible()
        ]

    async def _detect_elements_ocr(self):
        # Implement OCR-based element detection here
        pass

    def _get_element_description(self, element):
        description = element['inner_text'] or element['aria_label'] or element['placeholder'] or 'No description'
        return description.strip()

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
            tag = element['tag']
            element_type = element['type']

            mapped_type = 'input' if tag in ['input', 'textarea', 'select'] or (tag == 'input' and element_type in ['text', 'search', 'email', 'password', 'number']) else 'clickable'

            description = self._get_element_description(element)

            mapped[i] = {
                'element': element['element'],
                'bbox': element['bbox'],
                'type': mapped_type,
                'description': description
            }

            if self.show_visuals:
                await self._add_visual_marker(i, element['bbox'], mapped_type)

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

    async def scrape_page(self, url, max_retries=3):
        await self.setup_browser()

        for attempt in range(max_retries):
            try:
                print(f"Attempting to navigate to {url} (Attempt {attempt + 1}/{max_retries})")
                response = await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)

                if response.status >= 400:
                    print(f"Received HTTP status {response.status}. Retrying...")
                    continue

                print("Page loaded successfully. Mapping elements...")
                elements = await self.detect_elements(self.method)
                mapped_elements = await self.map_elements(elements)

                print("\n--- Mapped Elements ---")
                for num, info in mapped_elements.items():
                    print(f"{num}: {info['description']} ({info['type']})")
                print("------------------------\n")

                return mapped_elements, self.page.url

            except PlaywrightTimeoutError:
                print(f"Timeout occurred while loading the page. (Attempt {attempt + 1}/{max_retries})")
            except Exception as e:
                print(f"An error occurred while scraping {url}: {e}")

        print("Failed to scrape the page after maximum retries.")
        return None

    async def perform_action(self, action, mapped_elements):
        try:
            if "element" not in action or action["element"] not in mapped_elements:
                print(f"Element {action.get('element')} not found on the page.")
                return False

            element_info = mapped_elements[action["element"]]
            print(f"Attempting to perform {action['type']} on element {action['element']} ({element_info['description']})")

            if action["type"] == "click":
                await element_info['element'].click()
            elif action["type"] == "input":
                await element_info["element"].fill(action["text"])
                await self.page.keyboard.press("Enter")

            try:
                await self.page.wait_for_load_state("networkidle", timeout=30000)
                print("Page loaded after action.")
            except PlaywrightTimeoutError:
                print("Page load timed out after action. Continuing...")

            print(f"Successfully performed action: {action['type']} on element {action['element']}")
            return True

        except Exception as e:
            print(f"Error performing action: {str(e)}")
            return False

    async def cleanup(self):
        if self.browser:
            await self.browser.close()
        if self.playwright_instance:
            await self.playwright_instance.stop()


