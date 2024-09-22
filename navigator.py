from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import asyncio
import cv2
import numpy as np
import pytesseract
from PIL import Image

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
        elements = await self.page.query_selector_all('a, button, [role="button"], input, textarea, select')
        elements_data = []
        for elem in elements:
            if await elem.is_visible():
                bbox = await elem.bounding_box()
                if bbox:
                    elements_data.append({
                        'element': elem,
                        'bbox': bbox,
                        'tag': await elem.evaluate('el => el.tagName.toLowerCase()'),
                        'type': await elem.evaluate('el => el.type || ""'),
                        'placeholder': await elem.get_attribute('placeholder') or '',
                        'aria_label': await elem.get_attribute('aria-label') or '',
                        'inner_text': (await elem.inner_text()).strip() or await elem.get_attribute('value') or '',
                        'id': await elem.get_attribute('id') or ''
                    })
        return elements_data

async def _detect_elements_ocr(self):
    screenshot = await self.page.screenshot(full_page=True)
    
    nparr = np.frombuffer(screenshot, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    elements = []
    
    for i, contour in enumerate(contours):
        x, y, w, h = cv2.boundingRect(contour)
        roi = thresh[y:y+h, x:x+w]
        text = pytesseract.image_to_string(Image.fromarray(roi))
        if text.strip():
            element = await self.page.evaluate("""
                ([x, y, w, h]) => {
                    const element = document.elementFromPoint(x + w/2, y + h/2);
                    return element ? {
                        tag: element.tagName.toLowerCase(),
                        type: element.type || "",
                        placeholder: element.placeholder || "",
                        ariaLabel: element.getAttribute('aria-label') || "",
                        id: element.id || ""
                    } : null;
                }
            """, [x, y, w, h])
            
            if element:
                elements.append({
                    'element': await self.page.query_selector(f'#{element["id"]}') if element["id"] else None,
                    'bbox': {'x': x, 'y': y, 'width': w, 'height': h},
                    'tag': element['tag'],
                    'type': element['type'],
                    'placeholder': element['placeholder'],
                    'aria_label': element['ariaLabel'],
                    'inner_text': text.strip(),
                    'id': element['id'] or f'ocr_element_{i}'
                })
            else:
                elements.append({
                    'element': None,
                    'bbox': {'x': x, 'y': y, 'width': w, 'height': h},
                    'tag': 'ocr_element',
                    'type': 'unknown',
                    'placeholder': '',
                    'aria_label': '',
                    'inner_text': text.strip(),
                    'id': f'ocr_element_{i}'
                })
    
    return elements

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

            if description == 'No description':
                continue

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
        return self.browser.is_connected()

    async def navigate_to(self, url, max_retries=3):
        browser_connected = await self.setup_browser()
        if not browser_connected:
            self.logger.error("Failed to connect to the browser. Please check your setup.")
            return None

        for attempt in range(max_retries):
            try:
                self.logger.info(f"Attempting to navigate to {url} (Attempt {attempt + 1}/{max_retries})")
                response = await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)

                if response.status >= 400:
                    self.logger.warning(f"Received HTTP status {response.status}. Retrying...")
                    continue

                self.logger.info("Page loaded successfully. Mapping elements...")
                elements = await self.detect_elements()
                mapped_elements = await self.map_elements(elements)

                if self.verbose:
                    self.logger.debug("\n--- Mapped Elements ---")
                    for num, info in mapped_elements.items():
                        self.logger.debug(f"{num}: {info['description']} ({info['type']})")
                    self.logger.debug("------------------------\n")

                return mapped_elements, self.page.url

            except Exception as e:
                if "Target page, context or browser has been closed" in str(e):
                    self.logger.warning("Browser was closed unexpectedly. Attempting to reconnect...")
                    browser_connected = await self.setup_browser()
                    if not browser_connected:
                        self.logger.error("Failed to reconnect to the browser. Stopping the script.")
                        return None
                else:
                    self.logger.error(f"An error occurred while navigating to {url}: {e}")

        self.logger.error("Failed to navigate to the page after maximum retries.")
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