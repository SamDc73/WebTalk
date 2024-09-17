from visuals import scrape_page, interact_with_element, detect_elements, map_elements, get_element_description, add_visual_marker
from openai import AsyncOpenAI
import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import time
import os 
# client = AsyncOpenAI(
#     base_url="https://openrouter.ai/api/v1",
#     api_key="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",  # Replace with your actual OpenRouter API key
#     default_headers={"HTTP-Referer": "https://your-site.com"}  # Replace with your actual site URL
# )

def format_url(url):
    if not url.startswith(("http://", "https://")):
        return "https://" + url
    return url

class AutonomousWebAI:
    def __init__(self, openai_model, initial_prompt, method, show_visuals, openai_api_key):
        self.openai_model = openai_model
        self.initial_prompt = initial_prompt
        self.conversation_history = []
        self.method = method
        self.show_visuals = show_visuals
        self.action_history = []
        self.current_url = None
        self.playwright_instance = None
        self.browser = None
        self.context = None
        self.page = None
        self.client = AsyncOpenAI(api_key=openai_api_key)

    async def setup_browser(self):
        if not self.playwright_instance:
            self.playwright_instance = await async_playwright().start()
            self.browser = await self.playwright_instance.chromium.launch(headless=False)
            self.context = await self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                viewport={'width': 1280, 'height': 720}
            )
            self.page = await self.context.new_page()

    async def make_ai_decision(self, mapped_elements, task, current_url):
        elements_description = "\n".join(
            [f"{num}: {info['description']}" for num, info in mapped_elements.items()]
        )
        
        full_prompt = f"""Task: {task}
    Current URL: {current_url}
    Page elements:
    {elements_description}

    Decide the next action:
    - To click an element, respond with just the element number.
    - To input text, respond with the element number followed by a colon and the text to input.
    - If the task is complete, respond with "DONE".

    Your decision:"""

        try:
            response = await self.client.chat.completions.create(
                model=self.openai_model,
                messages=[{"role": "user", "content": full_prompt}]
            )
            decision = response.choices[0].message.content.strip()
            print(f"AI Decision: {decision}")
            return decision
        except Exception as e:
            print(f"Error with OpenAI model: {e}")
            return None

    async def run_web_scraper(self, url, max_retries=3):
        await self.setup_browser()  # Ensure browser is set up
        formatted_url = format_url(url)
        
        for attempt in range(max_retries):
            try:
                print(f"Attempting to navigate to {formatted_url} (Attempt {attempt + 1}/{max_retries})")
                response = await self.page.goto(formatted_url, wait_until="domcontentloaded", timeout=60000)
                
                if response.status >= 400:
                    print(f"Received HTTP status {response.status}. Retrying...")
                    continue

                print("Page loaded successfully. Mapping elements...")
                mapped_elements = await map_elements(self.page, await detect_elements(self.page, self.method), self.show_visuals)
                
                print("\n--- Mapped Elements ---")
                for num, info in mapped_elements.items():
                    print(f"{num}: {info['description']} ({info['type']})")
                print("------------------------\n")
                
                return mapped_elements, self.page.url

            except PlaywrightTimeoutError:
                print(f"Timeout occurred while loading the page. (Attempt {attempt + 1}/{max_retries})")
            except Exception as e:
                print(f"An error occurred while scraping {formatted_url}: {e}")
            
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5  # Exponential backoff
                print(f"Waiting for {wait_time} seconds before retrying...")
                time.sleep(wait_time)

        print("Failed to scrape the page after maximum retries.")
        return None


    def parse_decision(self, decision):
        if decision.upper() == "DONE":
            return None
        
        parts = decision.split(':', 1)
        try:
            element = int(parts[0])
            if len(parts) > 1:
                return {"type": "input", "element": element, "text": parts[1].strip()}
            else:
                return {"type": "click", "element": element}
        except ValueError:
            print(f"Invalid decision: {decision}")
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
                try:
                    await self.page.wait_for_load_state("networkidle", timeout=30000)
                    print("Page loaded after click.")
                except PlaywrightTimeoutError:
                    print("Page load timed out after click. Continuing...")

            elif action["type"] == "input":
                await element_info["element"].fill(action["text"])
                await self.page.keyboard.press("Enter")
                try:
                    await self.page.wait_for_load_state("networkidle", timeout=30000)
                    print("Page loaded after input.")
                except PlaywrightTimeoutError:
                    print("Page load timed out after input. Continuing...")

            if self.page.url != self.current_url:
                print(f"Page changed. New URL: {self.page.url}")
                self.current_url = self.page.url
            else:
                print("Stayed on the same page after action.")

            print(f"Successfully performed action: {action['type']} on element {action['element']}")
            return True

        except Exception as e:
            print(f"Error performing action: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
        
    async def parse_initial_message(self, message):
        try:
            response = await self.client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {"role": "system", "content": "You are an AI assistant that extracts the website URL and task from a given message. Respond with only the URL and task, separated by a newline."},
                    {"role": "user", "content": message}
                ]
            )
            url, task = response.choices[0].message.content.strip().split('\n')
            return url.strip(), task.strip()
        except Exception as e:
            print(f"Error parsing initial message: {e}")
            return None, None


    async def cleanup(self):
        if self.browser:
            await self.browser.close()
        if self.playwright_instance:
            await self.playwright_instance.stop()
            
    async def run(self, initial_message):
        url, task = await self.parse_initial_message(initial_message)
        if not url or not task:
            print("Failed to parse the initial message. Please provide a valid URL and task.")
            return

        self.current_url = url
        print(f"Starting URL: {self.current_url}")
        print(f"Task: {task}")

        max_iterations = 20
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            print(f"\n--- Iteration {iteration} ---")
            
            try:
                result = await self.run_web_scraper(self.current_url)
                if result is None:
                    print("Failed to scrape the page. Retrying...")
                    continue

                mapped_elements, new_url = result
                decision = await self.make_ai_decision(mapped_elements, task, new_url)

                if decision is None:
                    print("Failed to get a decision from AI model. Retrying...")
                    continue

                action = self.parse_decision(decision)
                if action is None:
                    print("Task completed or invalid decision. Stopping.")
                    break

                success = await self.perform_action(action, mapped_elements)
                if not success:
                    print("Failed to perform action. Retrying...")
                    continue

                self.current_url = self.page.url

            except PlaywrightTimeoutError:
                print("Page timed out. Moving to next iteration.")
            except Exception as e:
                print(f"Unexpected error: {str(e)}")
                break

        if iteration >= max_iterations:
            print("Maximum number of iterations reached. Stopping.")

        await self.cleanup()

async def main():
    ai = AutonomousWebAI(
        openai_model="gpt-4o",  # or whatever model you're using
        initial_prompt="You are an AI assistant tasked with navigating web pages and completing tasks.",
        method="ocr",
        show_visuals=True,
        openai_api_key=os.getenv("OPENAI_API_KEY")        
    )
    
    initial_message = "Go to amazon search for iphone 13 open the first product where the price is less than $500 then add to cart"
    
    await ai.run(initial_message)

if __name__ == "__main__":
    asyncio.run(main())
