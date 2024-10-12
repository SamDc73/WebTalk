import argparse
import asyncio

from decision_maker import DecisionMaker
from model_manager import ModelManager
from navigator import Navigator
from utils import format_url, get_logger, setup_logging


async def run_autonomous_web_ai(
    task: str,
    method: str,
    show_visuals: bool,
    verbose: bool,
    quiet: bool,
    model_manager: ModelManager,
) -> None:
    logger = get_logger()
    url, parsed_task = await model_manager.parse_initial_message(task)
    if not url or not parsed_task:
        logger.error("Failed to parse the initial message. Please provide a valid URL and task.")
        return

    logger.info(f"Starting URL: {url}")
    logger.info(f"Task: {parsed_task}")

    current_url = format_url(url)
    navigator = Navigator(method, show_visuals, verbose)
    decision_maker = DecisionMaker(model_manager, verbose)

    max_iterations = 20
    iteration = 0

    try:
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"\n--- Iteration {iteration} ---")

            result = await navigator.navigate_to(current_url)
            if result is None:
                logger.error("Navigation failed. Stopping the script.")
                break

            mapped_elements, new_url = result

            if verbose:
                print("\nMapped Elements:")
                for num, info in mapped_elements.items():
                    logger.info(f"{num}: {info['description']} ({info['type']})")

            decision = await decision_maker.make_decision(mapped_elements, parsed_task, new_url)
            if decision is None:
                logger.info("Task completed or no more actions available. Keeping browser open.")
                break

            logger.info(f"\nAI Decision: {decision}")

            actions = decision_maker.parse_decision(decision)
            if not actions:
                logger.info("No valid actions. Task may be completed. Keeping browser open.")
                break

            form_submitted = False
            for action_number, action in enumerate(actions, start=1):
                action_description = f"{action['type']} on {mapped_elements[action['element']]['description']}"
                logger.info(f"Action {action_number}: {action_description}")

                success = await navigator.perform_action(action, mapped_elements, action_number)
                if not success:
                    logger.error(f"Failed to perform action {action_number}: {action_description}")
                    continue

                if action['type'] == 'click' and mapped_elements[action['element']]['type'] == 'clickable':
                    form_submitted = True

            if not form_submitted and any(action['type'] == 'input' for action in actions):
                logger.info("Submitting form after input actions")
                await navigator.submit_form()

            current_url = navigator.page.url

            # Check if the task is completed after performing all actions
            task_completed = await decision_maker.is_task_completed(parsed_task, current_url)
            if task_completed:
                logger.info("Task completed successfully.")
                break

        logger.info("\nTask completed or max iterations reached. Keeping browser window open for 10 seconds.")
        await asyncio.sleep(10)

    except KeyboardInterrupt:
        logger.info("\nReceived keyboard interrupt. Closing browser.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        logger.exception(e)
    finally:
        logger.info("Closing browser.")
        await navigator.cleanup()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Autonomous Web AI")
    parser.add_argument("task", help="The task to perform")
    parser.add_argument(
        "--method", choices=["xpath", "ocr"], default="xpath", help="Method for element detection (default: xpath)"
    )
    parser.add_argument("--show-visuals", action="store_true", help="Show visual markers on the page")
    parser.add_argument("-v", "--verbose", action="store_true", help="Increase output verbosity")
    parser.add_argument("-q", "--quiet", action="store_true", help="Reduce output verbosity")
    parser.add_argument(
        "--model", choices=["openai", "groq"], default="openai", help="Choose the model provider (default: openai)"
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_arguments()
    setup_logging(args.verbose, args.quiet)
    logger = get_logger()

    model_manager = ModelManager.initialize(model_provider=args.model)

    try:
        await run_autonomous_web_ai(
            task=args.task,
            method=args.method,
            show_visuals=args.show_visuals,
            verbose=args.verbose,
            quiet=args.quiet,
            model_manager=model_manager,
        )
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt. Exiting.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        logger.exception(e)


if __name__ == "__main__":
    asyncio.run(main())
