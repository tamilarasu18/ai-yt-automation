"""
Structured Logging — Rich console for dev, JSON file for production.

Provides a unified logging setup with colored, timestamped output
via the Rich library and optional JSON-structured file logging.

Usage:
    from ai_shorts.core.logging import setup_logging, get_logger

    setup_logging()
    log = get_logger(__name__)
    log.info("Pipeline started", extra={"topic": "motivation"})
"""

from __future__ import annotations

import logging
import sys

_CONFIGURED = False


def setup_logging(level: int = logging.INFO, log_file: str | None = None) -> None:
    """Configure application-wide logging.

    Args:
        level: Logging level (default: INFO).
        log_file: Optional path for JSON file logging.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    root = logging.getLogger()
    root.setLevel(level)

    # Console handler with rich formatting
    try:
        from rich.logging import RichHandler

        console_handler = RichHandler(
            rich_tracebacks=True,
            show_time=True,
            show_path=False,
            markup=True,
        )
        console_handler.setFormatter(logging.Formatter("%(message)s"))
    except ImportError:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-7s | %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    console_handler.setLevel(level)
    root.addHandler(console_handler)

    # Optional JSON file handler for production
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter(
                '{"time": "%(asctime)s", "level": "%(levelname)s", '
                '"logger": "%(name)s", "message": "%(message)s"}',
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )
        file_handler.setLevel(level)
        root.addHandler(file_handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Get a named logger instance.

    Args:
        name: Logger name (typically __name__).

    Returns:
        Configured Logger instance.
    """
    return logging.getLogger(name)
