"""Logging configuration for TPC-H benchmark.

This module provides centralized logging configuration with support for:
- Environment-based log level control
- Debug mode toggle
- Structured logging format
- CloudWatch integration support
"""

import logging
import os
import sys


def setup_logging(
    name: str | None = None,
    level: str | None = None,
    format_string: str | None = None,
) -> logging.Logger:
    """Configure and return a logger instance.

    Args:
        name: Logger name (defaults to root logger if None)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               If None, reads from LOG_LEVEL env var, defaults to INFO.
        format_string: Custom format string for log messages.
                      If None, uses default structured format.

    Returns:
        Configured logger instance

    Example:
        >>> logger = setup_logging(__name__)
        >>> logger.info("Starting TPC-H data generation")
    """
    # Determine log level
    if level is None:
        level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Check if debug mode is enabled
    debug_mode = os.getenv("DEBUG", "false").lower() == "true"
    if debug_mode:
        level = "DEBUG"

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level))

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level))

    # Set format
    if format_string is None:
        format_string = (
            "%(asctime)s - %(name)s - %(levelname)s - "
            "%(funcName)s:%(lineno)d - %(message)s"
        )

    formatter = logging.Formatter(format_string)
    console_handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(console_handler)

    # Prevent propagation to root logger to avoid duplicate logs
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get or create a logger with standard configuration.

    This is a convenience function that wraps setup_logging with
    sensible defaults.

    Args:
        name: Logger name (typically __name__ from calling module)

    Returns:
        Configured logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing TPC-H query")
    """
    return setup_logging(name)


def enable_debug_logging() -> None:
    """Enable debug logging for all loggers.

    This function sets all existing loggers to DEBUG level.
    Useful for troubleshooting.

    Example:
        >>> enable_debug_logging()
        >>> logger.debug("This will now be visible")
    """
    logging.root.setLevel(logging.DEBUG)
    for handler in logging.root.handlers:
        handler.setLevel(logging.DEBUG)


def disable_debug_logging() -> None:
    """Disable debug logging and restore INFO level.

    Example:
        >>> disable_debug_logging()
        >>> logger.debug("This will be hidden")
    """
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.root.setLevel(getattr(logging, log_level))
    for handler in logging.root.handlers:
        handler.setLevel(getattr(logging, log_level))


def log_environment_info(logger: logging.Logger) -> None:
    """Log relevant environment configuration.

    Args:
        logger: Logger instance to use for output

    Example:
        >>> logger = get_logger(__name__)
        >>> log_environment_info(logger)
    """
    logger.info("Environment Configuration:")
    logger.info(f"  LOG_LEVEL: {os.getenv('LOG_LEVEL', 'INFO')}")
    logger.info(f"  DEBUG: {os.getenv('DEBUG', 'false')}")
    logger.info(f"  AWS_REGION: {os.getenv('AWS_REGION', 'not set')}")
    logger.info(f"  S3_BUCKET_NAME: {os.getenv('S3_BUCKET_NAME', 'not set')}")
    logger.info(f"  TPCH_SCALE_FACTOR: {os.getenv('TPCH_SCALE_FACTOR', 'not set')}")


# Example usage
if __name__ == "__main__":
    # Basic usage
    logger = get_logger(__name__)
    logger.info("This is an info message")
    logger.debug("This debug message won't show unless DEBUG=true")

    # Enable debug mode
    enable_debug_logging()
    logger.debug("Now this debug message will show")

    # Log environment info
    log_environment_info(logger)
