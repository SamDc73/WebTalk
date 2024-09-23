import argparse
import asyncio
from dotenv import load_dotenv
from navigator import Navigator
from decision_maker import DecisionMaker
from utils import format_url, parse_initial_message, setup_logging, check_api_key
from model_manager import ModelManager

async def run_autonomous_web_ai(task, method, show_visuals, verbose, quiet, logger, model_manager):
    url, parsed_task = await parse_initial_message(model_manager.client, model_manager.model, task)
    if not url or not parsed_task:
        print("Failed to parse the initial message. Please provide a valid URL and task.")
        return

    print(f"Starting URL: {url}")
    print(f"Task: {parsed_task}")

    current_url = format_url(url)
    navigator = Navigator(method, show_visuals, logger, verbose)
    decision_maker = DecisionMaker(model_manager.client, model_manager.model, logger, verbose)

    max_iterations = 20
    iteration = 0

    try:
        while iteration < max_iterations:
            iteration += 1
            print(f"\n--- Iteration {iteration} ---")

            result = await navigator.navigate_to(current_url)
            if result is None:
                print("Navigation failed. Stopping the script.")
                break

            mapped_elements, new_url = result

            # Print mapped elements
            print("\nMapped Elements:")
            for num, info in mapped_elements.items():
                print(f"{num}: {info['description']} ({info['type']})")

            decision = await decision_maker.make_decision(mapped_elements, parsed_task, new_url)

            if decision is None:
                print("Failed to get a decision from AI model. Stopping.")
                break

            print(f"\nAI Decision: {decision}")

            action = decision_maker.parse_decision(decision)
            if action is None:
                print("Task completed or invalid decision. Keeping browser open.")
                break

            action_description = f"{action['type']} on {mapped_elements[action['element']]['description']}"
            print(f"Action: {action_description}")

            success = await navigator.perform_action(action, mapped_elements)
            if not success:
                print("Failed to perform action. Stopping.")
                break

            current_url = navigator.page.url

        print("\nTask completed. Keeping browser window open for 10 seconds.")
        await asyncio.sleep(10)
    
    except KeyboardInterrupt:
        print("\nReceived keyboard interrupt. Closing browser.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        print("Closing browser.")
        await navigator.cleanup()

def parse_arguments():
    parser = argparse.ArgumentParser(description="Autonomous Web AI")
    parser.add_argument("task", help="The task to perform")
    parser.add_argument("--method", choices=["xpath", "ocr"], default="xpath", help="Method for element detection (default: xpath)")
    parser.add_argument("--show-visuals", action="store_true", help="Show visual markers on the page")
    parser.add_argument("-v", "--verbose", action="store_true", help="Increase output verbosity")
    parser.add_argument("-q", "--quiet", action="store_true", help="Reduce output verbosity")
    return parser.parse_args()

async def main():
    load_dotenv()
    args = parse_arguments()
    logger = setup_logging(args.verbose, args.quiet)

    api_key = check_api_key()
    model_manager = ModelManager(api_key, "gpt-4")

    try:
        await run_autonomous_web_ai(
            task=args.task,
            method=args.method,
            show_visuals=args.show_visuals,
            verbose=args.verbose,
            quiet=args.quiet,
            logger=logger,
            model_manager=model_manager
        )
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt. Exiting.")

if __name__ == "__main__":
    asyncio.run(main())