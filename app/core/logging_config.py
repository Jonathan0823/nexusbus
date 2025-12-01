"""Structured logging configuration."""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor


def add_log_level(logger: logging.Logger, method_name: str, event_dict: EventDict) -> EventDict:
    """Add log level to event dict."""
    if method_name == "warn":
        method_name = "warning"
    event_dict["level"] = method_name.upper()
    return event_dict


def add_timestamp(logger: logging.Logger, method_name: str, event_dict: EventDict) -> EventDict:
    """Add timestamp to event dict."""
    import datetime
    event_dict["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"
    return event_dict


def setup_logging(
    log_level: str = "INFO",
    use_json: bool = False,
    include_caller_info: bool = True,
) -> None:
    """Setup structured logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        use_json: If True, output JSON format (for production). If False, use colored console output.
        include_caller_info: If True, include caller information (filename, line number, function)
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )
    
    # Build processors list
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,  # Merge context variables
        add_timestamp,  # Add timestamp
        add_log_level,  # Add log level
        structlog.stdlib.add_logger_name,  # Add logger name
    ]
    
    if include_caller_info:
        processors.append(structlog.processors.add_log_level)  # Add log level again for caller info
        processors.append(structlog.processors.StackInfoRenderer())  # Add stack info
        processors.append(
            structlog.processors.format_exc_info  # Format exceptions
        )
    
    if use_json:
        # JSON output for production/log aggregation
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Human-readable colored output for development
        processors.append(
            structlog.dev.ConsoleRenderer(colors=True)
        )
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured structlog logger
        
    Example:
        logger = get_logger(__name__)
        logger.info("user_login", user_id=123, ip_address="192.168.1.1")
    """
    return structlog.get_logger(name)

