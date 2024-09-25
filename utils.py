import logging
import os
from datetime import datetime


logging.getLogger("litellm").setLevel(logging.WARNING)
    
    
def format_url(url):
    if not url.startswith(("http://", "https://")):
        return "https://" + url
    return url

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

