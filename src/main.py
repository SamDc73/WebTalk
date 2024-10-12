import argparse
import asyncio

from decision_maker import DecisionMaker
from model_manager import ModelManager
from navigator import Navigator
from utils import format_url, get_logger, setup_logging


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


async def execute_task(task: str, navigator: Navigator, decision_maker: DecisionMaker) -> None:
    logger = get_logger()
    url, parsed_task = await decision_maker.model_manager.parse_initial_message(task)
    if not url or not parsed_task:
        logger.error("Failed to parse initial message")
        return

    url = format_url(url)
    logger.info(f"Navigating to: {url}")
    logger.info(f"Task: {parsed_task}")

    result = await navigator.navigate_to(url)
    if not result:
        logger.error("Failed to navigate to the URL")
        return

    mapped_elements, current_url = result

    while True:
        decision = await decision_maker.make_decision(mapped_elements, parsed_task, current_url)
        if not decision:
            logger.error("Failed to get a decision from the AI")
            break

        actions = decision_maker.parse_decision(decision)
        if not actions:
            logger.info("Task completed or no further actions required")
            break

        for i, action in enumerate(actions, 1):
            success = await navigator.perform_action(action, mapped_elements, i)
            if not success:
                logger.error(f"Failed to perform action {i}")
                break

        result = await navigator.navigate_to(navigator.page.url)
        if not result:
            logger.error("Failed to update page elements after action")
            break

        mapped_elements, current_url = result

        if await decision_maker.is_task_completed(parsed_task, current_url):
            logger.info("Task completed successfully")
            break

    logger.info("Task execution completed")


async def main() -> None:
    args = parse_arguments()
    setup_logging(args.verbose, args.quiet)
    logger = get_logger()

    try:
        model_manager = ModelManager.initialize(model_provider=args.model)
        navigator = Navigator(args.method, args.show_visuals, args.verbose)
        decision_maker = DecisionMaker(model_manager, args.verbose)

        await execute_task(args.task, navigator, decision_maker)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt. Exiting.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        logger.exception(e)
    finally:
        if "navigator" in locals():
            await navigator.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
