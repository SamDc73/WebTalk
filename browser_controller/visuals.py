from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import time



def capture_screenshot(page):
    return page.screenshot()


def map_elements(page):
    mapped = {}
    counter = 1

    def add_numbered_box(element, color):
        nonlocal counter
        bounding_box = element.bounding_box()
        if bounding_box:
            x, y = bounding_box['x'], bounding_box['y']
            page.evaluate(f"""
                var div = document.createElement('div');
                div.textContent = '{counter}';
                div.style.position = 'absolute';
                div.style.left = '{x}px';
                div.style.top = '{y}px';
                div.style.backgroundColor = '{color}';
                div.style.border = '1px solid black';
                div.style.padding = '2px';
                div.style.zIndex = '9999';
                document.body.appendChild(div);
            """)
            mapped[counter] = {
                'element': element,
                'type': 'input' if color == 'red' else 'clickable',
                'description': element.inner_text() or element.get_attribute('aria-label') or element.get_attribute('placeholder') or f"Element {counter}"
            }
            counter += 1

    # Add functionality to detect images
    image_elements = page.query_selector_all('img')
    for element in image_elements:
        add_numbered_box(element, 'blue')  # Use a different color for images

    clickable_elements = page.query_selector_all('a, button, [role="button"]')
    for element in clickable_elements:
        add_numbered_box(element, 'yellow')

    input_elements = page.query_selector_all('input[type="text"], input[type="search"], textarea')
    for element in input_elements:
        add_numbered_box(element, 'red')

    return mapped

def print_layout(mapped):
    for number, info in mapped.items():
        print(f"{number}: {info['description']} ({'Input' if info['type'] == 'input' else 'Clickable'})")

def interact_with_page(page, mapped):
    while True:
        print("\nEnter a number to interact with an element, or 'q' to quit:")
        choice = input().strip()
        
        if choice.lower() == 'q':
            return False
        
        try:
            number = int(choice)
            if number in mapped:
                element_info = mapped[number]
                try:
                    if element_info['type'] == 'input':
                        print(f"Enter text for {element_info['description']}:")
                        text = input().strip()
                        element_info['element'].fill(text)
                        page.keyboard.press('Enter')
                    else:
                        element_info['element'].click()
                        page.keyboard.press('Enter')
                except PlaywrightTimeoutError:
                    print("Interaction timed out. The page might have changed.")
                except Exception as e:
                    print(f"An error occurred: {e}")
                    print("The page might have changed. Continuing...")
                return True  # Re-map elements after any interaction attempt
            else:
                print("Invalid number. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number or 'q'.")

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        current_url = "https://www.google.com"
        page.goto(current_url)
        
        while True:
            if page.url != current_url:
                print("Page changed. Remapping elements...")
                current_url = page.url
            
            mapped = map_elements(page)
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