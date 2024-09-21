import logging
import os
from datetime import datetime

def format_url(url):
    if not url.startswith(("http://", "https://")):
        return "https://" + url
    return url

async def parse_initial_message(client, model, message):
    try:
        response = await client.chat.completions.create(
            model=model,
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