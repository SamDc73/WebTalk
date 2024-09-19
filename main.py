import argparse
import asyncio
import logging
import os
from datetime import datetime
from autonomous_web_ai import AutonomousWebAI
from dotenv import load_dotenv

def setup_logging(verbose, quiet):
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"webai_{timestamp}.log")

    if quiet:
        console_level = logging.WARNING
    elif verbose:
        console_level = logging.DEBUG
    else:
        console_level = logging.INFO

    # Create a logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # Create handlers
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)

    # Create formatters and add it to handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

def parse_arguments():
    parser = argparse.ArgumentParser(description="Autonomous Web AI")
    parser.add_argument("task", help="The task to perform")
    parser.add_argument("--method", choices=["xpath", "ocr"], default="xpath", help="Method for element detection (default: xpath)")
    parser.add_argument("--show-visuals", action="store_true", help="Show visual markers on the page")
    parser.add_argument("-v", "--verbose", action="store_true", help="Increase output verbosity")
    parser.add_argument("-q", "--quiet", action="store_true", help="Reduce output verbosity")
    return parser.parse_args()

def check_api_key():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("API key not found. Please check your .env file.")
        new_key = input("Enter your OpenAI API key: ")
        os.environ["OPENAI_API_KEY"] = new_key
        with open(".env", "a") as f:
            f.write(f"\nOPENAI_API_KEY={new_key}")
        print("API key has been saved to .env file.")
    return os.getenv("OPENAI_API_KEY")



def setup_logging(verbose, quiet):
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"webai_{timestamp}.log")

    # Set up logging configuration
    if quiet:
        console_level = logging.ERROR
    elif verbose:
        console_level = logging.DEBUG
    else:
        console_level = logging.INFO

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

    # Get the root logger
    logger = logging.getLogger()

    # Set the level for the console handler
    logger.handlers[1].setLevel(console_level)

    return logger

async def main():
    load_dotenv()
    args = parse_arguments()
    logger = setup_logging(args.verbose, args.quiet)

    api_key = check_api_key()

    ai = AutonomousWebAI(
        openai_model="gpt-4o",
        initial_prompt="You are an AI assistant tasked with navigating web pages and completing tasks.",
        method=args.method,
        show_visuals=args.show_visuals,
        openai_api_key=api_key,
        logger=logger,
        verbose=args.verbose,
        quiet=args.quiet
    )
    
    try:
        await ai.run(args.task)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt. Exiting.")
    finally:
        await ai.web_scraper.cleanup()
        
        
if __name__ == "__main__":
    asyncio.run(main())