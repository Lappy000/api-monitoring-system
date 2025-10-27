"""Edge case and error handling tests."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.health_checker import HealthChecker, HealthCheckResult
from app.models.endpoint import Endpoint
from app.utils.retry import retry_with_backoff, RetryError


@pytest.mark.unit
class TestNetworkErrors:
    """Test network error handling."""
    
    async def test_connection_timeout(self, sample_endpoint: Endpoint):
        """Test handling of connection timeout."""
        checker = HealthChecker(default_timeout=1)
        await checker.start()
        
        try:
            # Use unreachable IP to force timeout
            sample_endpoint.url = "http://192.0.2.1:9999"  # TEST-NET-1, should timeout
            sample_endpoint.timeout = 1
            
            result = await checker.check_endpoint(sample_endpoint, use_retry=False)
            
            assert result.success is False
            assert result.error_message is not None
            # Check for timeout or timed in message
            assert result.error_message is not None
            assert ("timeout" in result.error_message.lower() or
                    "timed" in result.error_message.lower() or
                    "error" in result.error_message.lower())
        
        finally:
            await checker.close()
    
    async def test_connection_refused(self, sample_endpoint: Endpoint):
        """Test handling of connection refused."""
        checker = HealthChecker()
        await checker.start()
        
        try:
            # Use localhost with wrong port
            sample_endpoint.url = "http://localhost:9999"
            
            result = await checker.check_endpoint(sample_endpoint, use_retry=False)
            
            assert result.success is False
            assert result.error_message is not None
        
        finally:
            await checker.close()
    
    async def test_dns_failure(self, sample_endpoint: Endpoint):
        """Test handling of DNS resolution failure."""
        checker = HealthChecker()
        await checker.start()
        
        try:
            # Use non-existent domain
            sample_endpoint.url = "http://this-domain-definitely-does-not-exist-12345.com"
            
            result = await checker.check_endpoint(sample_endpoint, use_retry=False)
            
            assert result.success is False
            assert result.error_message is not None
        
        finally:
            await checker.close()


@pytest.mark.unit
class TestMalformedInputs:
    """Test handling of malformed inputs."""
    
    async def test_invalid_url_format(self, sample_endpoint: Endpoint):
        """Test handling of invalid URL format."""
        checker = HealthChecker()
        await checker.start()
        
        try:
            # Invalid URL format
            sample_endpoint.url = "not-a-valid-url"
            
            result = await checker.check_endpoint(sample_endpoint, use_retry=False)
            
            assert result.success is False
            assert result.error_message is not None
        
        finally:
            await checker.close()
    
    async def test_empty_url(self, sample_endpoint: Endpoint):
        """Test handling of empty URL."""
        checker = HealthChecker()
        await checker.start()
        
        try:
            sample_endpoint.url = ""
            
            result = await checker.check_endpoint(sample_endpoint, use_retry=False)
            
            assert result.success is False
        
        finally:
            await checker.close()
    
    async def test_invalid_http_method(self, sample_endpoint: Endpoint):
        """Test handling of invalid HTTP method."""
        checker = HealthChecker()
        await checker.start()
        
        try:
            # aiohttp should still handle this, but let's verify
            sample_endpoint.method = "INVALID"
            sample_endpoint.url = "https://httpbin.org/status/200"
            
            result = await checker.check_endpoint(sample_endpoint, use_retry=False)
            
            # Result depends on server, but should not crash
            assert result is not None
        
        finally:
            await checker.close()


@pytest.mark.unit
class TestStatusCodeMismatches:
    """Test handling of unexpected status codes."""
    
    async def test_404_not_found(self, sample_endpoint: Endpoint):
        """Test handling of 404 status code."""
        checker = HealthChecker()
        await checker.start()
        
        try:
            sample_endpoint.url = "https://httpbin.org/status/404"
            sample_endpoint.expected_status = 200
            
            result = await checker.check_endpoint(sample_endpoint, use_retry=False)
            
            assert result.success is False
            assert result.status_code == 404
            assert "Expected status 200, got 404" in result.error_message
        
        finally:
            await checker.close()
    
    async def test_500_server_error(self, sample_endpoint: Endpoint):
        """Test handling of 500 status code."""
        checker = HealthChecker()
        await checker.start()
        
        try:
            sample_endpoint.url = "https://httpbin.org/status/500"
            sample_endpoint.expected_status = 200
            
            result = await checker.check_endpoint(sample_endpoint, use_retry=False)
            
            assert result.success is False
            assert result.status_code == 500
        
        finally:
            await checker.close()
    
    async def test_redirect_not_expected(self, sample_endpoint: Endpoint):
        """Test handling of redirect when not expected."""
        checker = HealthChecker()
        await checker.start()
        
        try:
            # httpbin follows redirects automatically, so we'll get 200
            sample_endpoint.url = "https://httpbin.org/redirect/1"
            sample_endpoint.expected_status = 200
            
            result = await checker.check_endpoint(sample_endpoint, use_retry=False)
            
            # Should succeed as redirects are followed
            assert result.status_code == 200
        
        finally:
            await checker.close()


@pytest.mark.unit  
class TestRetryMechanism:
    """Test retry mechanism with various failures."""
    
    async def test_retry_exhaustion(self):
        """Test that retries are exhausted on persistent failures."""
        call_count = 0
        
        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")
        
        with pytest.raises(RetryError):
            await retry_with_backoff(
                always_fail,
                max_attempts=3,
                base_delay=0.1,
                exceptions=(ValueError,)
            )
        
        assert call_count == 3
    
    async def test_retry_success_on_second_attempt(self):
        """Test successful retry on second attempt."""
        call_count = 0
        
        async def fail_once():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First attempt fails")
            return "success"
        
        result = await retry_with_backoff(
            fail_once,
            max_attempts=3,
            base_delay=0.1,
            exceptions=(ValueError,)
        )
        
        assert result == "success"
        assert call_count == 2
    
    async def test_retry_with_different_exception(self):
        """Test that retry doesn't catch unexpected exceptions."""
        async def wrong_exception():
            raise KeyError("Not in retry list")
        
        # Should not retry KeyError if only catching ValueError
        with pytest.raises(KeyError):
            await retry_with_backoff(
                wrong_exception,
                max_attempts=3,
                base_delay=0.1,
                exceptions=(ValueError,)
            )


@pytest.mark.unit
class TestConcurrencyEdgeCases:
    """Test concurrent access edge cases."""
    
    async def test_multiple_simultaneous_checks(self, sample_endpoint: Endpoint):
        """Test multiple simultaneous checks don't interfere."""
        checker = HealthChecker(max_concurrent=10)
        await checker.start()
        
        try:
            # Run 10 checks concurrently
            tasks = [
                checker.check_endpoint(sample_endpoint, use_retry=False)
                for _ in range(10)
            ]
            
            results = await asyncio.gather(*tasks)
            
            # All should complete
            assert len(results) == 10
            assert all(isinstance(r, HealthCheckResult) for r in results)
        
        finally:
            await checker.close()
    
    async def test_checker_reuse(self, sample_endpoint: Endpoint):
        """Test that health checker can be reused multiple times."""
        checker = HealthChecker()
        await checker.start()
        
        try:
            # First check
            result1 = await checker.check_endpoint(sample_endpoint, use_retry=False)
            
            # Second check with same checker
            result2 = await checker.check_endpoint(sample_endpoint, use_retry=False)
            
            # Both should work
            assert result1 is not None
            assert result2 is not None
        
        finally:
            await checker.close()


@pytest.mark.unit
class TestDatabaseEdgeCases:
    """Test database-related edge cases."""
    
    async def test_duplicate_endpoint_name(self, db_session: AsyncSession):
        """Test handling of duplicate endpoint names."""
        endpoint1 = Endpoint(
            name="Duplicate",
            url="https://example.com/1",
            method="GET",
            interval=60,
            timeout=5,
            expected_status=200
        )
        
        endpoint2 = Endpoint(
            name="Duplicate",  # Same name
            url="https://example.com/2",
            method="GET",
            interval=60,
            timeout=5,
            expected_status=200
        )
        
        db_session.add(endpoint1)
        await db_session.commit()
        
        # Second endpoint with same name should cause constraint violation
        db_session.add(endpoint2)
        
        with pytest.raises(Exception):  # Should raise IntegrityError
            await db_session.commit()
    
    async def test_cascade_delete(self, db_session: AsyncSession, sample_endpoint: Endpoint):
        """Test that deleting endpoint cascades to check results."""
        from app.models.check_result import CheckResult
        from sqlalchemy import select
        
        # Add check result
        check = CheckResult(
            endpoint_id=sample_endpoint.id,
            status_code=200,
            response_time=0.1,
            success=True
        )
        db_session.add(check)
        await db_session.commit()
        
        check_id = check.id
        
        # Delete endpoint
        await db_session.delete(sample_endpoint)
        await db_session.commit()
        
        # Check result should also be deleted
        result = await db_session.execute(
            select(CheckResult).where(CheckResult.id == check_id)
        )
        deleted_check = result.scalar_one_or_none()
        
        assert deleted_check is None


@pytest.mark.unit
class TestConfigurationEdgeCases:
    """Test configuration edge cases."""
    
    def test_missing_required_config(self):
        """Test handling of missing required configuration."""
        from app.config import EndpointConfig
        
        # Missing required fields should raise validation error
        with pytest.raises(Exception):  # Pydantic ValidationError
            EndpointConfig(name="Test")  # Missing url, method, etc.
    
    def test_invalid_interval(self):
        """Test handling of invalid interval values."""
        from app.schemas.endpoint import EndpointCreate
        from pydantic import ValidationError
        
        # Negative interval should fail validation (ge=10 in schema)
        with pytest.raises(ValidationError):
            config = EndpointCreate(
                name="Test",
                url="https://example.com",
                method="GET",
                interval=5,  # Less than minimum of 10
                timeout=5,
                expected_status=200
            )
    
    def test_invalid_status_code(self):
        """Test handling of invalid status code."""
        from app.schemas.endpoint import EndpointCreate
        from pydantic import ValidationError
        
        # Invalid status code should fail validation (le=599 in schema)
        with pytest.raises(ValidationError):
            config = EndpointCreate(
                name="Test",
                url="https://example.com",
                method="GET",
                interval=60,
                timeout=5,
                expected_status=600  # Greater than maximum of 599
            )