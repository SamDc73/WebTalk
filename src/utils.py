import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import yaml


# Suppress litellm debug messages
logging.getLogger("litellm").setLevel(logging.WARNING)


def format_url(url: str) -> str:
    """
    Ensure the URL starts with 'https://' if no protocol is specified.

    Parameters
    ----------
    url : str
        The input URL.

    Returns
    -------
    str
        The formatted URL with 'https://' prepended if necessary.
    """
    return f"https://{url}" if not url.startswith(("http://", "https://")) else url


def setup_logging(verbose: bool, quiet: bool) -> logging.Logger:
    """
    Set up logging configuration based on verbosity settings.

    Parameters
    ----------
    verbose : bool
        If True, set console logging level to DEBUG.
    quiet : bool
        If True, set console logging level to ERROR.

    Returns
    -------
    logging.Logger
        Configured logger instance.
    """
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"webai_{timestamp}.log")

    # Define log levels
    file_level = logging.DEBUG
    console_level: Literal["DEBUG", "INFO", "ERROR"] = "ERROR" if quiet else "DEBUG" if verbose else "INFO"

    # Create a custom logger
    logger = logging.getLogger("webai")
    logger.setLevel(logging.DEBUG)

    # Create handlers
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(file_level)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, console_level))

    # Create formatters and add it to handlers
    file_format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    console_format = logging.Formatter("%(levelname)s: %(message)s")
    file_handler.setFormatter(file_format)
    console_handler.setFormatter(console_format)

    # Add handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def get_logger() -> logging.Logger:
    """
    Get the configured logger instance.

    Returns
    -------
    logging.Logger
        The configured logger instance.
    """
    return logging.getLogger("webai")


def extract_domain(url: str) -> str:
    """
    Extract the domain from a given URL.

    Parameters
    ----------
    url : str
        The URL to extract the domain from.

    Returns
    -------
    str
        The extracted domain.
    """
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    if domain.startswith("www."):
        domain = domain[4:]
    return domain

def load_prompt(analyzer_name: str) -> dict:
    prompt_path = Path(__file__).parent.parent / "prompts" / f"{analyzer_name}.yaml"
    with open(prompt_path, "r") as f:
        return yaml.safe_load(f)


def format_prompt(prompt: dict, **kwargs) -> dict:
    return {"system_message": prompt["system_message"], "user_message": prompt["user_message"].format(**kwargs)}


def extract_key_value_pairs(task: str) -> dict[str, str]:
    pattern = r"(\w+(?:\s+\w+)*)\s+(?:is|it's|are)\s+['\"]?([\w@.]+)['\"]?"
    return dict(re.findall(pattern, task, re.IGNORECASE))
