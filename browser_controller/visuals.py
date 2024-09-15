from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import cv2
import numpy as np
import time
import argparse

def parse_arguments():
    parser = argparse.ArgumentParser(description="Web page interaction script with multiple detection methods")
    parser.add_argument('--no-visuals', action='store_true', help="Disable visual markers on the page")
    parser.add_argument('--method', choices=['default', 'ocr', 'xpath'], default='default',
                        help="Element detection method: default, ocr, or xpath")
    return parser.parse_args()

def capture_screenshot(page):
    screenshot = page.screenshot()
    nparr = np.frombuffer(screenshot, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return img

def detect_elements_default(page):
    elements = page.query_selector_all('a, button, [role="button"], input, textarea, select')
    return [
        {
            'element': elem,
            'bbox': elem.bounding_box(),
            'tag': elem.evaluate('el => el.tagName.toLowerCase()'),
            'type': elem.evaluate('el => el.type'),
            'placeholder': elem.get_attribute('placeholder'),
            'aria_label': elem.get_attribute('aria-label'),
            'inner_text': elem.inner_text()
        }
        for elem in elements if elem.is_visible()
    ]

def detect_elements_ocr(page):
    # Placeholder for OCR-based element detection
    # This would involve capturing a screenshot and using OCR to identify interactive elements
    print("OCR-based element detection is not implemented in this example.")
    return detect_elements_default(page)

def detect_elements_xpath(page):
    # Placeholder for XPath-based element detection
    # This would involve using XPath queries to identify interactive elements
    print("XPath-based element detection is not implemented in this example.")
    return detect_elements_default(page)

def get_element_description(element):
    description = element['inner_text'] or element['aria_label'] or element['placeholder'] or 'No description'
    return description.strip()

def add_visual_marker(page, number, bbox, element_type):
    color = 'red' if element_type == 'input' else 'yellow'
    page.evaluate(f"""() => {{
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

def map_elements(page, elements, show_visuals=True):
    mapped = {}
    for i, element in enumerate(elements, 1):
        tag = element['tag']
        element_type = element['type']
        
        if tag == 'input' and element_type in ['text', 'search', 'email', 'password', 'number']:
            mapped_type = 'input'
        elif tag in ['textarea', 'select']:
            mapped_type = 'input'
        else:
            mapped_type = 'clickable'
        
        description = get_element_description(element)
        
        mapped[i] = {
            'element': element['element'],
            'bbox': element['bbox'],
            'type': mapped_type,
            'description': description
        }
        
        if show_visuals:
            add_visual_marker(page, i, element['bbox'], mapped_type)
    
    return mapped

def print_layout(mapped):
    for number, info in mapped.items():
        print(f"{number}: {info['description']} ({info['type']})")

def interact_with_element(page, element_info):
    try:
        if element_info['type'] == 'input':
            print(f"Enter text for {element_info['description']}:")
            text = input().strip()
            element_info['element'].fill(text)
            page.keyboard.press('Enter')
        else:
            element_info['element'].click()
    except PlaywrightTimeoutError:
        print("Interaction timed out. The page might have changed.")
    except Exception as e:
        print(f"An error occurred: {e}")
        print("The page might have changed. Continuing...")

def interact_with_page(page, mapped):
    while True:
        print("\nEnter a number to interact with an element, or 'q' to quit:")
        choice = input().strip()
        
        if choice.lower() == 'q':
            return False
        
        try:
            number = int(choice)
            if number in mapped:
                interact_with_element(page, mapped[number])
                return True  # Re-map elements after any interaction
            else:
                print("Invalid number. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number or 'q'.")

def main():
    args = parse_arguments()
    show_visuals = not args.no_visuals

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        current_url = "https://www.google.com"
        page.goto(current_url)
        
        detection_methods = {
            'default': detect_elements_default,
            'ocr': detect_elements_ocr,
            'xpath': detect_elements_xpath
        }
        
        detect_elements = detection_methods[args.method]
        
        while True:
            if page.url != current_url:
                print("Page changed. Remapping elements...")
                current_url = page.url
            
            elements = detect_elements(page)
            mapped = map_elements(page, elements, show_visuals)
            
            print("\nMapped elements:")
            print_layout(mapped)
            
            should_remap = interact_with_page(page, mapped)
            if should_remap:
                time.sleep(2)  # Wait for potential page load
                continue
            else:
                break
        
        print("Closing browser.")
        browser.close()

if __name__ == "__main__":
    main()