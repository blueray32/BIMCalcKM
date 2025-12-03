import logging
import os
import sys
from typing import Any

import structlog
from pathlib import Path


def configure_logging() -> None:
    """Configure structured logging for the application."""
    
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if os.getenv("JSON_LOGS", "false").lower() == "true":
        # Production: JSON logs
        processors = shared_processors + [
            structlog.processors.JSONRenderer()
        ]
    else:
        # Development: Pretty console logs
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer()
        ]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging to use structlog
    handlers = [logging.StreamHandler(sys.stdout)]
    
    # Add FileHandler if logs directory exists
    log_file = Path("logs/bimcalc.log")
    if log_file.parent.exists():
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        format="%(message)s",
        handlers=handlers,
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
