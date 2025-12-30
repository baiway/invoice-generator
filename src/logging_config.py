"""
Logging configuration for the invoice generator.

This module sets up structured logging with appropriate levels and formatting.
Detailed logs are written to a file, while console output is kept minimal.
"""

import logging
import sys
from pathlib import Path

from src.constants import LOG_FILE


def setup_logging(level: int = logging.INFO) -> str:
    """
    Configure logging for the application.

    Logs are written to a file with full detail, while console output
    is kept minimal (WARNING and above only) to avoid cluttering the
    progress bars.

    Args:
        level: Logging level for file output (default: INFO)

    Returns:
        Path to the log file where detailed logs are written
    """
    # Create formatters
    detailed_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # File handler - logs everything at INFO level and above
    file_handler = logging.FileHandler(LOG_FILE, mode='w')
    file_handler.setLevel(level)
    file_handler.setFormatter(detailed_formatter)

    # Console handler - only show WARNING and above to keep output clean
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(detailed_formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Suppress verbose third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)
    logging.getLogger("google.auth").setLevel(logging.WARNING)
    logging.getLogger("fontTools").setLevel(logging.CRITICAL)
    logging.getLogger("fontTools.subset").setLevel(logging.CRITICAL)
    logging.getLogger("fontTools.ttLib").setLevel(logging.CRITICAL)
    logging.getLogger("weasyprint").setLevel(logging.CRITICAL)

    return str(Path(LOG_FILE).resolve())


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    Args:
        name: Module name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
