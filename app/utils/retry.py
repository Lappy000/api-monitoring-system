"""Retry mechanism with exponential backoff for handling transient failures."""

import asyncio
import random
from functools import wraps
from typing import Callable, TypeVar, Any, Optional, Tuple, Type
from app.utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class RetryError(Exception):
    """Exception raised when all retry attempts have failed."""
    pass


async def retry_with_backoff(
    func: Callable[..., T],
    *args: Any,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    multiplier: float = 2.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    **kwargs: Any
) -> T:
    """
    Execute an async function with exponential backoff retry logic.
    
    Args:
        func: Async function to execute
        *args: Positional arguments for func
        max_attempts: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        multiplier: Multiplier for exponential backoff
        max_delay: Maximum delay in seconds
        jitter: Whether to add random jitter to delay
        exceptions: Tuple of exception types to catch and retry
        **kwargs: Keyword arguments for func
        
    Returns:
        Result of the function call
        
    Raises:
        RetryError: If all retry attempts fail
        
    Example:
        ```python
        result = await retry_with_backoff(
            fetch_data,
            url="https://api.example.com",
            max_attempts=3,
            base_delay=1.0
        )
        ```
    """
    last_exception: Optional[Exception] = None
    
    for attempt in range(1, max_attempts + 1):
        try:
            logger.debug(
                f"Attempting function call",
                extra={
                    "function": func.__name__,
                    "attempt": attempt,
                    "max_attempts": max_attempts
                }
            )
            result = await func(*args, **kwargs)
            
            if attempt > 1:
                logger.info(
                    f"Function succeeded after retry",
                    extra={
                        "function": func.__name__,
                        "attempt": attempt
                    }
                )
            
            return result
            
        except exceptions as e:
            last_exception = e
            
            if attempt == max_attempts:
                logger.error(
                    f"Function failed after all retry attempts",
                    extra={
                        "function": func.__name__,
                        "attempts": max_attempts,
                        "error": str(e)
                    }
                )
                break
            
            # Calculate delay with exponential backoff
            delay = min(base_delay * (multiplier ** (attempt - 1)), max_delay)
            
            # Add jitter if enabled
            if jitter:
                delay = delay * (0.5 + random.random())
            
            logger.warning(
                f"Function failed, retrying",
                extra={
                    "function": func.__name__,
                    "attempt": attempt,
                    "max_attempts": max_attempts,
                    "delay": delay,
                    "error": str(e)
                }
            )
            
            await asyncio.sleep(delay)
    
    raise RetryError(
        f"Function {func.__name__} failed after {max_attempts} attempts. "
        f"Last error: {last_exception}"
    ) from last_exception


def async_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    multiplier: float = 2.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Decorator for adding retry logic to async functions.
    
    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        multiplier: Multiplier for exponential backoff
        max_delay: Maximum delay in seconds
        jitter: Whether to add random jitter to delay
        exceptions: Tuple of exception types to catch and retry
        
    Returns:
        Decorated function with retry logic
        
    Example:
        ```python
        @async_retry(max_attempts=3, base_delay=1.0)
        async def fetch_data(url: str) -> dict:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    return await response.json()
        ```
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await retry_with_backoff(
                func,
                *args,
                max_attempts=max_attempts,
                base_delay=base_delay,
                multiplier=multiplier,
                max_delay=max_delay,
                jitter=jitter,
                exceptions=exceptions,
                **kwargs
            )
        return wrapper
    return decorator


class RetryConfig:
    """Configuration class for retry behavior."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        multiplier: float = 2.0,
        max_delay: float = 60.0,
        jitter: bool = True
    ):
        """
        Initialize retry configuration.
        
        Args:
            max_attempts: Maximum number of retry attempts
            base_delay: Initial delay in seconds
            multiplier: Multiplier for exponential backoff
            max_delay: Maximum delay in seconds
            jitter: Whether to add random jitter to delay
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.multiplier = multiplier
        self.max_delay = max_delay
        self.jitter = jitter
    
    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for a given attempt number.
        
        Args:
            attempt: Current attempt number (1-indexed)
            
        Returns:
            Delay in seconds
        """
        delay = min(
            self.base_delay * (self.multiplier ** (attempt - 1)),
            self.max_delay
        )
        
        if self.jitter:
            delay = delay * (0.5 + random.random())
        
        return delay