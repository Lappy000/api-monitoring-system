"""Tests for Circuit Breaker pattern."""

import pytest
import asyncio
from unittest.mock import AsyncMock

from app.core.circuit_breaker import CircuitBreaker, CircuitBreakerError, CircuitState


@pytest.mark.unit
class TestCircuitBreaker:
    """Test Circuit Breaker functionality."""
    
    def test_circuit_breaker_init(self):
        """Test circuit breaker initialization."""
        cb = CircuitBreaker(
            name="test_circuit",
            failure_threshold=5,
            recovery_timeout=60,
            expected_exception=Exception
        )
        
        assert cb.failure_threshold == 5
        assert cb.recovery_timeout == 60
        assert cb.failure_count == 0
        assert cb.state == CircuitState.CLOSED
    
    async def test_successful_call_keeps_circuit_closed(self):
        """Test that successful calls keep circuit closed."""
        cb = CircuitBreaker(name="test_circuit", failure_threshold=3)
        
        async def successful_func():
            return "success"
        
        result = await cb.call(successful_func)
        
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
    
    async def test_failures_open_circuit(self):
        """Test that repeated failures open the circuit."""
        cb = CircuitBreaker(name="test_circuit", failure_threshold=3)
        
        async def failing_func():
            raise Exception("Test failure")
        
        # First 3 failures should accumulate
        for i in range(3):
            with pytest.raises(Exception):
                await cb.call(failing_func)
        
        # Circuit should now be open
        assert cb.state == CircuitState.OPEN
        
        # Next call should raise CircuitBreakerError without calling func
        with pytest.raises(CircuitBreakerError):
            await cb.call(failing_func)
    
    async def test_circuit_recovers_after_timeout(self):
        """Test circuit moves to half-open after recovery timeout."""
        cb = CircuitBreaker(
            name="test_circuit",
            failure_threshold=2,
            recovery_timeout=0.1  # 100ms for fast testing
        )
        
        async def failing_func():
            raise Exception("Test failure")
        
        # Trigger circuit to open
        for _ in range(2):
            with pytest.raises(Exception):
                await cb.call(failing_func)
        
        assert cb.state == CircuitState.OPEN
        
        # Wait for recovery timeout
        await asyncio.sleep(0.15)
        
        # Next call should attempt (half-open state)
        # but will fail again
        with pytest.raises(Exception):
            await cb.call(failing_func)
        
        # Should be open again
        assert cb.state == CircuitState.OPEN
    
    async def test_half_open_success_closes_circuit(self):
        """Test successful call in half-open state closes circuit."""
        cb = CircuitBreaker(
            name="test_circuit",
            failure_threshold=2,
            recovery_timeout=0.1,
            success_threshold=1  # Only need 1 success to close
        )
        
        call_count = 0
        
        async def conditional_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("Fail first 2 times")
            return "success"
        
        # Open the circuit
        for _ in range(2):
            with pytest.raises(Exception):
                await cb.call(conditional_func)
        
        assert cb.state == CircuitState.OPEN
        
        # Wait for recovery
        await asyncio.sleep(0.15)
        
        # This should succeed and close the circuit
        result = await cb.call(conditional_func)
        
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
    
    async def test_circuit_breaker_with_custom_exception(self):
        """Test circuit breaker with custom exception type."""
        
        class CustomError(Exception):
            pass
        
        cb = CircuitBreaker(
            name="test_circuit",
            failure_threshold=2,
            expected_exception=CustomError
        )
        
        async def func_custom_error():
            raise CustomError("Custom failure")
        
        async def func_other_error():
            raise ValueError("Other error")
        
        # CustomError should count as failure
        with pytest.raises(CustomError):
            await cb.call(func_custom_error)
        
        assert cb.failure_count == 1
        
        # Other exceptions should not count
        with pytest.raises(ValueError):
            await cb.call(func_other_error)
        
        assert cb.failure_count == 1  # Should not increase
    
    async def test_get_health_check_circuit_breaker(self):
        """Test getting circuit breaker for health checks."""
        from app.core.circuit_breaker import get_health_check_circuit_breaker
        
        cb1 = get_health_check_circuit_breaker("endpoint1")
        cb2 = get_health_check_circuit_breaker("endpoint1")
        cb3 = get_health_check_circuit_breaker("endpoint2")
        
        # Same endpoint should return same instance
        assert cb1 is cb2
        
        # Different endpoint should return different instance
        assert cb1 is not cb3


@pytest.mark.integration
class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker."""
    
    async def test_circuit_breaker_protects_against_cascading_failures(self):
        """Test circuit breaker prevents cascading failures."""
        cb = CircuitBreaker(name="test_circuit", failure_threshold=3, recovery_timeout=0.2)
        
        call_count = 0
        max_calls = 10
        
        async def flaky_service():
            nonlocal call_count
            call_count += 1
            if call_count <= 5:
                raise Exception("Service down")
            return "OK"
        
        failures = 0
        circuit_breaker_blocks = 0
        
        for _ in range(max_calls):
            try:
                await cb.call(flaky_service)
            except CircuitBreakerError:
                circuit_breaker_blocks += 1
            except Exception:
                failures += 1
            
            await asyncio.sleep(0.05)
        
        # Circuit breaker should have blocked some calls
        assert circuit_breaker_blocks > 0
        # Not all calls should have hit the flaky service
        assert call_count < max_calls