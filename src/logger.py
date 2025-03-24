"""
Centralized logging configuration module for the chat application
"""

import logging
from logging.handlers import RotatingFileHandler
import os


def setup_logger(service_name, log_file=None):
    """
    Configure and return a logger with both console and file handlers

    Args:
        service_name: Name of the service (server, replica1, etc.)
        log_file: Path to log file. If None, defaults to logs/{service_name}.log

    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)

    if log_file is None:
        # Use replica ID from env var if available
        replica_id = os.environ.get("REPLICA_ID", "")
        if replica_id and service_name == "replica":
            log_file = f"logs/replica_server_{replica_id}.log"
        else:
            log_file = f"logs/{service_name}.log"

    # Configure logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Remove existing handlers if they exist (to avoid duplicate entries)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Create file handler for rotating logs (10MB max size, keep 5 backup files)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5
    )
    file_handler.setLevel(logging.INFO)

    # Create formatter and add it to the handlers
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    # Add handlers to logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
