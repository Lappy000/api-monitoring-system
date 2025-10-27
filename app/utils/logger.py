"""Structured logging utility with JSON and text format support."""

import logging
import sys
from pathlib import Path
from typing import Optional
import structlog
from pythonjsonlogger import jsonlogger


def setup_logging(
    level: str = "INFO",
    log_format: str = "json",
    log_file: Optional[str] = None,
    console: bool = True
) -> None:
    """
    Configure structured logging for the application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Format type ("json" or "text")
        log_file: Path to log file (None for no file logging)
        console: Whether to log to console
        
    Example:
        ```python
        setup_logging(level="INFO", log_format="json", log_file="logs/app.log")
        logger = get_logger(__name__)
        logger.info("Application started", extra={"version": "1.0.0"})
        ```
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create handlers list
    handlers = []
    
    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        if log_format == "json":
            console_handler.setFormatter(
                jsonlogger.JsonFormatter(
                    '%(timestamp)s %(level)s %(name)s %(message)s',
                    timestamp=True
                )
            )
        else:
            console_handler.setFormatter(
                logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
            )
        handlers.append(console_handler)
    
    # File handler
    if log_file:
        # Create log directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        if log_format == "json":
            file_handler.setFormatter(
                jsonlogger.JsonFormatter(
                    '%(timestamp)s %(level)s %(name)s %(message)s',
                    timestamp=True
                )
            )
        else:
            file_handler.setFormatter(
                logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
            )
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        handlers=handlers,
        force=True
    )
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given name.
    
    Args:
        name: Logger name (usually __name__ of the module)
        
    Returns:
        logging.Logger: Configured logger instance
        
    Example:
        ```python
        logger = get_logger(__name__)
        logger.info("Processing endpoint", endpoint_id=123, url="https://api.example.com")
        logger.error("Check failed", endpoint_id=123, error="Timeout")
        ```
    """
    return logging.getLogger(name)


class LoggerMixin:
    """
    Mixin class to add logging capability to any class.
    
    Example:
        ```python
        class MyService(LoggerMixin):
            def process(self):
                self.logger.info("Processing started")
        ```
    """
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger for this class."""
        return get_logger(self.__class__.__name__)