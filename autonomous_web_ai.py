from web_tools import WebTools
from ai_decision import AIDecisionMaker
from utils import format_url, parse_initial_message
from openai import AsyncOpenAI

class AutonomousWebAI:
    def __init__(self, openai_model, initial_prompt, method, show_visuals, openai_api_key):
        self.openai_model = openai_model
        self.initial_prompt = initial_prompt
        self.method = method
        self.show_visuals = show_visuals
        self.client = AsyncOpenAI(api_key=openai_api_key)
        self.web_scraper = WebTools(method, show_visuals)
        self.ai_decision_maker = AIDecisionMaker(self.client, openai_model)

    async def run(self, initial_message):
        url, task = await parse_initial_message(self.client, self.openai_model, initial_message)
        if not url or not task:
            print("Failed to parse the initial message. Please provide a valid URL and task.")
            return

        current_url = format_url(url)
        print(f"Starting URL: {current_url}")
        print(f"Task: {task}")

        max_iterations = 20
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            print(f"\n--- Iteration {iteration} ---")

            result = await self.web_scraper.scrape_page(current_url)
            if result is None:
                print("Failed to scrape the page. Retrying...")
                continue

            mapped_elements, new_url = result
            decision = await self.ai_decision_maker.make_decision(mapped_elements, task, new_url)

            if decision is None:
                print("Failed to get a decision from AI model. Retrying...")
                continue

            action = self.ai_decision_maker.parse_decision(decision)
            if action is None:
                print("Task completed or invalid decision. Stopping.")
                break

            success = await self.web_scraper.perform_action(action, mapped_elements)
            if not success:
                print("Failed to perform action. Retrying...")
                continue

            current_url = self.web_scraper.page.url

        if iteration >= max_iterations:
            print("Maximum number of iterations reached. Stopping.")

        await self.web_scraper.cleanup()
