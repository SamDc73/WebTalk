import logging
import os
from datetime import datetime
from typing import Literal


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

    console_level: Literal["DEBUG", "INFO", "ERROR"] = "ERROR" if quiet else "DEBUG" if verbose else "INFO"

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),
        ],
    )

    logger = logging.getLogger()
    logger.handlers[1].setLevel(getattr(logging, console_level))

    return logger
