from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import cv2
import numpy as np
import asyncio

async def setup_browser(self):
    if not self.playwright_instance:
        self.playwright_instance = await async_playwright().start()
        self.browser = await self.playwright_instance.chromium.launch(headless=False)
        self.context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            viewport={'width': 1280, 'height': 720}
        )
        self.page = await self.context.new_page()

def capture_screenshot(page):
    screenshot = page.screenshot()
    nparr = np.frombuffer(screenshot, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return img

async def detect_elements(page, method='xpath'):
    if method == 'ocr':
        return await detect_elements_default(page)
    else:
        return await detect_elements_default(page)

async def detect_elements_default(page):
    elements = await page.query_selector_all('a, button, [role="button"], input, textarea, select')
    return [
        {
            'element': elem,
            'bbox': await elem.bounding_box(),
            'tag': await elem.evaluate('el => el.tagName.toLowerCase()'),
            'type': await elem.evaluate('el => el.type'),
            'placeholder': await elem.get_attribute('placeholder'),
            'aria_label': await elem.get_attribute('aria-label'),
            'inner_text': await elem.inner_text(),
            'id': await elem.get_attribute('id')  # Add this line
        }
        for elem in elements if await elem.is_visible()
    ]

def get_element_description(element):
    description = element['inner_text'] or element['aria_label'] or element['placeholder'] or 'No description'
    return description.strip()

async def add_visual_marker(page, number, bbox, element_type):
    color = 'red' if element_type == 'input' else 'yellow'
    await page.evaluate(f"""() => {{
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

async def map_elements(page, elements, show_visuals=True):
    mapped = {}
    for i, element in enumerate(elements, 1):
        tag = element['tag']
        element_type = element['type']
        
        mapped_type = 'input' if tag in ['input', 'textarea', 'select'] or (tag == 'input' and element_type in ['text', 'search', 'email', 'password', 'number']) else 'clickable'
        
        description = get_element_description(element)
        
        mapped[i] = {
            'element': element['element'],
            'bbox': element['bbox'],
            'type': mapped_type,
            'description': description
        }
        
        if show_visuals:
            await add_visual_marker(page, i, element['bbox'], mapped_type)
    
    return mapped

def print_layout(mapped):
    for number, info in mapped.items():
        print(f"{number}: {info['description']} ({info['type']})")

async def interact_with_element(page, element_info):
    try:
        if element_info['type'] == 'input':
            print(f"Enter text for {element_info['description']}:")
            text = input().strip()
            await element_info['element'].fill(text)
            async with page.expect_navigation(timeout=5000):
                await page.keyboard.press('Enter')
        else:
            async with page.expect_navigation(timeout=5000):
                await element_info['element'].click()
    except PlaywrightTimeoutError:
        print("Navigation timed out. The page might not have changed.")
    except Exception as e:
        print(f"An error occurred: {e}")
        print("The page might have changed. Continuing...")



async def scrape_page(url, method='xpath', show_visuals=True, max_retries=3):
    p, browser, page = await setup_browser()
    
    for attempt in range(max_retries):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            print(f"Current page: {page.url}")
            
            elements = await detect_elements(page, method)
            
            if not elements:
                print("No elements detected.")
                return None
            
            mapped = await map_elements(page, elements, show_visuals)
            
            print("\nMapped elements:")
            print_layout(mapped)
            
            return mapped, page.url, page, browser, p
        
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 1000  # Exponential backoff
                print(f"Retrying in {wait_time/1000} seconds...")
                await asyncio.sleep(wait_time / 1000)
            else:
                print(f"Max retries reached. Failed to scrape {url}")
                await browser.close()
                await p.stop()
                return None

