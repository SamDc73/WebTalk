import argparse
import asyncio

from analyzers.text_analyzer import TextAnalyzer
from decision_maker import DecisionMaker
from model_manager import ModelManager
from navigator import Navigator
from plugins.plugin_manager import PluginManager
from utils import format_url, get_logger, setup_logging


async def execute_task(
    task: str,
    navigator: Navigator,
    decision_maker: DecisionMaker,
    plugin_manager: PluginManager,
) -> None:
    logger = get_logger()
    url, parsed_task = await decision_maker.analyzer.model_manager.parse_initial_message(task)
    if not url or not parsed_task:
        logger.error("Failed to parse initial message")
        return

    url = format_url(url)
    logger.info("Navigating to: %s", url)
    logger.info("Task: %s", parsed_task)

    try:
        mapped_elements, current_url = await navigator.navigate_to(url, plugin_manager)
    except Exception as e:
        logger.error(f"Failed to navigate to the URL: {e}")
        return

    while True:
        await plugin_manager.handle_event("pre_decision", {"url": current_url, "elements": mapped_elements})
        plugin_data = await plugin_manager.pre_decision({"url": current_url, "elements": mapped_elements})

        decision = await decision_maker.make_decision(mapped_elements, parsed_task, current_url, plugin_data)

        if not decision:
            logger.error("Failed to get a decision from the AI")
            break

        actions = decision_maker.parse_decision(decision)
        if not actions:
            logger.info("Task completed or no further actions required")
            break

        await plugin_manager.handle_event(
            "post_decision",
            {"decision": decision, "url": current_url, "elements": mapped_elements},
        )
        await plugin_manager.post_decision(decision, {"url": current_url, "elements": mapped_elements})

        all_actions_successful = True
        for action in actions:
            action_result = await navigator.perform_action(action, mapped_elements, plugin_manager)
            if not action_result:
                logger.error("Failed to perform action: %s", action)
                all_actions_successful = False
                break

        if not all_actions_successful:
            break

        result = await navigator.navigate_to(navigator.page.url, plugin_manager)
        if not result:
            logger.error("Failed to update page elements after actions")
            break

        mapped_elements, current_url = result

        if await decision_maker.is_task_completed(parsed_task, current_url):
            logger.info("Task completed successfully")
            break

    logger.info("Task execution completed")

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Autonomous Web AI")
    parser.add_argument("task", help="The task to perform")
    parser.add_argument(
        "--method",
        choices=["xpath", "ocr"],
        default="xpath",
        help="Method for element detection (default: xpath)",
    )
    parser.add_argument("--show-visuals", action="store_true", help="Show visual markers on the page")
    parser.add_argument("-v", "--verbose", action="store_true", help="Increase output verbosity")
    parser.add_argument("-q", "--quiet", action="store_true", help="Reduce output verbosity")
    parser.add_argument(
        "--model",
        choices=["openai", "groq"],
        default="openai",
        help="Choose the model provider (default: openai)",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_arguments()
    setup_logging(args.verbose, args.quiet)
    logger = get_logger()

    try:
        model_manager = ModelManager.initialize(model_provider=args.model)

        # Choose the appropriate analyzer based on args or config
        analyzer = TextAnalyzer(model_manager)
        # analyzer = VisionAnalyzer(model_manager)

        navigator = Navigator(
            headless=False,  # You might want to make this configurable
            detection_method=args.method,
            show_visuals=args.show_visuals,
        )
        decision_maker = DecisionMaker(model_manager, analyzer, args.verbose)

        plugin_manager = PluginManager("src/plugins", "config/plugins.json")
        await plugin_manager.load_plugins()

        async with navigator:
            await execute_task(args.task, navigator, decision_maker, plugin_manager)

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt. Exiting.")
    except Exception:
        logger.exception("An unexpected error occurred")
    finally:
        if "plugin_manager" in locals():
            await plugin_manager.cleanup_plugins()


if __name__ == "__main__":
    asyncio.run(main())
