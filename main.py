import argparse
import asyncio
from autonomous_web_ai import AutonomousWebAI
from dotenv import load_dotenv
import os

def parse_arguments():
    parser = argparse.ArgumentParser(description="Autonomous Web AI")
    parser.add_argument("task", help="The task to perform")
    parser.add_argument("--method", choices=["xpath", "ocr"], default="xpath", help="Method for element detection (default: xpath)")
    parser.add_argument("--show-visuals", action="store_true", help="Show visual markers on the page")
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


async def main():
    load_dotenv()
    args = parse_arguments()

    api_key = check_api_key()

    ai = AutonomousWebAI(
        openai_model="gpt-4o",
        initial_prompt="You are an AI assistant tasked with navigating web pages and completing tasks.",
        method=args.method,
        show_visuals=args.show_visuals,
        openai_api_key=api_key
    )
    
    await ai.run(args.task)

if __name__ == "__main__":
    asyncio.run(main())
