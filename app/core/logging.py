"""
Application Logging Setup.
Configures structured console and rotating file logs for debugging and audits.
"""
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path


def setup_logging(app):
    """Configures handlers, formatters, and log levels for the Flask app."""
    log_level_name = app.config.get("LOG_LEVEL", "INFO")
    log_level = getattr(logging, log_level_name.upper(), logging.INFO)

    log_file = app.config.get("LOG_FILE")
    if log_file:
        log_dir = Path(log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8"
        )
        file_formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d]: %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(log_level)
        app.logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(log_level)
    app.logger.addHandler(console_handler)

    app.logger.setLevel(log_level)
    app.logger.info(f"RecruitFlow AI logging initialized at level {log_level_name}")
