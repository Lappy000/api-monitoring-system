"""Circuit breaker pattern implementation for fault tolerance."""

import asyncio
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Any, Optional, Dict
from functools import wraps
import time

from app.utils.logger import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open and rejecting requests."""
    pass


class CircuitBreaker:
    """
    Circuit breaker for preventing cascading failures.
    
    The circuit breaker monitors calls to external services and opens the circuit
    when the failure rate exceeds a threshold, preventing further calls until
    the service recovers.
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
        success_threshold: int = 3
    ):
        """
        Initialize circuit breaker.
        
        Args:
            name: Circuit breaker name (for logging)
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds before attempting recovery
            expected_exception: Exception type to count as failure
            success_threshold: Number of successes to close circuit in half-open state
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.success_threshold = success_threshold
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self._lock = asyncio.Lock()
        
        logger.info(
            f"Circuit breaker initialized",
            extra={
                "circuit_name": name,
                "failure_threshold": failure_threshold,
                "recovery_timeout": recovery_timeout
            }
        )
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with circuit breaker protection.
        
        Args:
            func: Function to call
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Any: Function result
            
        Raises:
            CircuitBreakerError: If circuit is open
            Exception: If function fails
        """
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if await self._should_attempt_reset():
                    logger.warning(
                        f"🟡 Circuit breaker entering HALF_OPEN state for recovery attempt",
                        extra={
                            "circuit_name": self.name,
                            "previous_state": "OPEN",
                            "new_state": "HALF_OPEN",
                            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
                            "success_threshold": self.success_threshold
                        }
                    )
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                else:
                    time_since_failure = (datetime.utcnow() - self.last_failure_time).total_seconds() if self.last_failure_time else 0
                    logger.debug(
                        f"Circuit breaker still OPEN, not ready for recovery",
                        extra={
                            "circuit_name": self.name,
                            "time_since_failure": time_since_failure,
                            "recovery_timeout": self.recovery_timeout
                        }
                    )
                    raise CircuitBreakerError(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        f"Last failure: {self.last_failure_time}. "
                        f"Will retry in {self.recovery_timeout - time_since_failure:.0f}s"
                    )
        
        try:
            # Call the function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Success - update circuit state
            await self._on_success()
            return result
            
        except self.expected_exception as e:
            # Expected failure - update circuit state
            await self._on_failure()
            raise e
        
        except Exception as e:
            # Unexpected failure - don't count as failure for custom exception handlers
            # Only count if expected_exception is Exception (the default)
            if self.expected_exception == Exception:
                await self._on_failure()
            raise e
    
    async def _on_success(self) -> None:
        """Handle successful call."""
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                logger.debug(
                    f"Circuit breaker success in HALF_OPEN state",
                    extra={
                        "circuit_name": self.name,
                        "success_count": self.success_count,
                        "success_threshold": self.success_threshold
                    }
                )
                if self.success_count >= self.success_threshold:
                    logger.warning(
                        f"🟢 Circuit breaker CLOSING after successful recovery",
                        extra={
                            "circuit_name": self.name,
                            "success_count": self.success_count,
                            "previous_state": "HALF_OPEN",
                            "new_state": "CLOSED"
                        }
                    )
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
            elif self.state == CircuitState.CLOSED:
                # Reset failure count on success in closed state
                if self.failure_count > 0:
                    logger.debug(
                        f"Circuit breaker resetting failure count",
                        extra={
                            "circuit_name": self.name,
                            "previous_failures": self.failure_count
                        }
                    )
                self.failure_count = 0
    
    async def _on_failure(self) -> None:
        """Handle failed call."""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.utcnow()
            
            if self.state == CircuitState.HALF_OPEN:
                # Failed in half-open state, go back to open
                logger.error(
                    f"🔴 Circuit breaker REOPENING after failure in HALF_OPEN state",
                    extra={
                        "circuit_name": self.name,
                        "failure_count": self.failure_count,
                        "previous_state": "HALF_OPEN",
                        "new_state": "OPEN",
                        "recovery_timeout": self.recovery_timeout
                    }
                )
                self.state = CircuitState.OPEN
                self.success_count = 0
            
            elif self.state == CircuitState.CLOSED:
                logger.warning(
                    f"Circuit breaker failure recorded",
                    extra={
                        "circuit_name": self.name,
                        "failure_count": self.failure_count,
                        "threshold": self.failure_threshold,
                        "state": "CLOSED"
                    }
                )
                if self.failure_count >= self.failure_threshold:
                    logger.error(
                        f"🔴 Circuit breaker OPENING due to failure threshold exceeded",
                        extra={
                            "circuit_name": self.name,
                            "failure_count": self.failure_count,
                            "threshold": self.failure_threshold,
                            "previous_state": "CLOSED",
                            "new_state": "OPEN",
                            "recovery_timeout": self.recovery_timeout
                        }
                    )
                    self.state = CircuitState.OPEN
    
    async def _should_attempt_reset(self) -> bool:
        """
        Check if enough time has passed to attempt recovery.
        
        Returns:
            bool: True if recovery timeout has elapsed
        """
        if not self.last_failure_time:
            return True
        
        time_since_failure = datetime.utcnow() - self.last_failure_time
        return time_since_failure.total_seconds() >= self.recovery_timeout
    
    def get_state(self) -> Dict[str, Any]:
        """
        Get current circuit breaker state.
        
        Returns:
            Dict[str, Any]: State information
        """
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout
        }


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""
    
    def __init__(self):
        """Initialize circuit breaker registry."""
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
    
    def get_circuit_breaker(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
        success_threshold: int = 3
    ) -> CircuitBreaker:
        """
        Get or create a circuit breaker.
        
        Args:
            name: Circuit breaker name
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds before attempting recovery
            expected_exception: Exception type to count as failure
            success_threshold: Number of successes to close circuit
            
        Returns:
            CircuitBreaker: Circuit breaker instance
        """
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                expected_exception=expected_exception,
                success_threshold=success_threshold
            )
        
        return self.circuit_breakers[name]
    
    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """
        Get state of all circuit breakers.
        
        Returns:
            Dict[str, Dict[str, Any]]: States of all circuit breakers
        """
        return {
            name: cb.get_state()
            for name, cb in self.circuit_breakers.items()
        }
    
    async def reset_circuit_breaker(self, name: str) -> bool:
        """
        Reset a circuit breaker to closed state.
        
        Args:
            name: Circuit breaker name
            
        Returns:
            bool: True if reset successful
        """
        if name in self.circuit_breakers:
            async with self._lock:
                cb = self.circuit_breakers[name]
                cb.state = CircuitState.CLOSED
                cb.failure_count = 0
                cb.success_count = 0
                cb.last_failure_time = None
            
            logger.info(
                f"Circuit breaker manually reset",
                extra={"circuit_name": name}
            )
            return True
        
        return False
    
    async def reset_all(self) -> None:
        """Reset all circuit breakers."""
        async with self._lock:
            for name, cb in self.circuit_breakers.items():
                cb.state = CircuitState.CLOSED
                cb.failure_count = 0
                cb.success_count = 0
                cb.last_failure_time = None
            
            logger.info(f"All circuit breakers manually reset")


# Global circuit breaker registry
circuit_breaker_registry = CircuitBreakerRegistry()


def with_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    expected_exception: type = Exception,
    success_threshold: int = 3
):
    """
    Decorator to apply circuit breaker to a function.
    
    Args:
        name: Circuit breaker name
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds before attempting recovery
        expected_exception: Exception type to count as failure
        success_threshold: Number of successes to close circuit
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cb = circuit_breaker_registry.get_circuit_breaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                expected_exception=expected_exception,
                success_threshold=success_threshold
            )
            
            return await cb.call(func, *args, **kwargs)
        
        return wrapper
    
    return decorator


# Pre-configured circuit breakers for common use cases
def get_health_check_circuit_breaker(endpoint_name: str) -> CircuitBreaker:
    """
    Get circuit breaker for health check operations.
    
    Args:
        endpoint_name: Endpoint name
        
    Returns:
        CircuitBreaker: Configured circuit breaker
    """
    return circuit_breaker_registry.get_circuit_breaker(
        name=f"health_check_{endpoint_name}",
        failure_threshold=3,
        recovery_timeout=30,
        expected_exception=Exception,
        success_threshold=2
    )


def get_notification_circuit_breaker(notification_type: str) -> CircuitBreaker:
    """
    Get circuit breaker for notification operations.
    
    Args:
        notification_type: Type of notification (email, webhook, telegram)
        
    Returns:
        CircuitBreaker: Configured circuit breaker
    """
    return circuit_breaker_registry.get_circuit_breaker(
        name=f"notification_{notification_type}",
        failure_threshold=5,
        recovery_timeout=60,
        expected_exception=Exception,
        success_threshold=3
    )


def get_database_circuit_breaker() -> CircuitBreaker:
    """
    Get circuit breaker for database operations.
    
    Returns:
        CircuitBreaker: Configured circuit breaker
    """
    return circuit_breaker_registry.get_circuit_breaker(
        name="database",
        failure_threshold=3,
        recovery_timeout=30,
        expected_exception=Exception,
        success_threshold=2
    )