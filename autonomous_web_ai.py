from web_tools import WebTools
from ai_decision import AIDecisionMaker
from utils import format_url, parse_initial_message
from openai import AsyncOpenAI
import asyncio


class AutonomousWebAI:
    def __init__(self, openai_model, initial_prompt, method, show_visuals, openai_api_key, logger, verbose, quiet):
        self.openai_model = openai_model
        self.initial_prompt = initial_prompt
        self.method = method
        self.show_visuals = show_visuals
        self.client = AsyncOpenAI(api_key=openai_api_key)
        self.logger = logger
        self.verbose = verbose
        self.web_scraper = WebTools(method, show_visuals, logger, verbose)
        self.ai_decision_maker = AIDecisionMaker(self.client, openai_model, logger, verbose)
        self.quiet = quiet


    async def run(self, initial_message):
        url, task = await parse_initial_message(self.client, self.openai_model, initial_message)
        if not url or not task:
            self.logger.error("Failed to parse the initial message. Please provide a valid URL and task.")
            return

        if not self.quiet:
            print(f"Starting URL: {url}")
            print(f"Task: {task}")

        current_url = format_url(url)
        self.logger.info(f"Starting URL: {current_url}")
        self.logger.info(f"Task: {task}")

        max_iterations = 20
        iteration = 0

        try:
            while iteration < max_iterations:
                iteration += 1
                if not self.quiet:
                    print(f"\n--- Iteration {iteration} ---")

                result = await self.web_scraper.scrape_page(current_url)
                if result is None:
                    self.logger.error("Scraping failed. Stopping the script.")
                    break

                mapped_elements, new_url = result
                decision = await self.ai_decision_maker.make_decision(mapped_elements, task, new_url)

                if decision is None:
                    self.logger.error("Failed to get a decision from AI model. Stopping.")
                    break

                action = self.ai_decision_maker.parse_decision(decision)
                if action is None:
                    if not self.quiet:
                        print("Task completed or invalid decision. Keeping browser open.")
                    break

                if not self.quiet:
                    action_description = f"{action['type']} on {mapped_elements[action['element']]['description']}"
                    print(f"Action: {action_description}")

                success = await self.web_scraper.perform_action(action, mapped_elements)
                if not success:
                    self.logger.error("Failed to perform action. Stopping.")
                    break

                current_url = self.web_scraper.page.url

            if not self.quiet:
                print("\nTask completed. Keeping browser window open for 10 seconds.")
            
            # Wait for 10 seconds
            await asyncio.sleep(10)
        
        except KeyboardInterrupt:
            if not self.quiet:
                print("\nReceived keyboard interrupt. Closing browser.")
        except Exception as e:
            self.logger.error(f"An unexpected error occurred: {e}")
        finally:
            if not self.quiet:
                print("Closing browser.")
            await self.web_scraper.cleanup()
