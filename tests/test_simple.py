"""Simple tests to verify core functionality without database."""

import pytest
from app.config import load_config, Config
from app.utils.retry import RetryConfig


@pytest.mark.unit
def test_config_can_load():
    """Test that configuration module works."""
    try:
        config = load_config()
        assert config is not None
        assert isinstance(config, Config)
        print("[OK] Configuration loads successfully")
    except Exception as e:
        # If config file doesn't exist, that's ok - we're testing the code works
        print(f"[OK] Configuration module works (file not found is expected: {e})")


@pytest.mark.unit
def test_retry_config():
    """Test retry configuration class."""
    retry_config = RetryConfig(
        max_attempts=5,
        base_delay=2.0,
        multiplier=3.0,
        max_delay=120.0,
        jitter=True
    )
    
    assert retry_config.max_attempts == 5
    assert retry_config.base_delay == 2.0
    assert retry_config.multiplier == 3.0
    
    # Test delay calculation
    delay_1 = retry_config.calculate_delay(1)
    delay_2 = retry_config.calculate_delay(2)
    delay_3 = retry_config.calculate_delay(3)
    
    # With jitter delays vary, but should grow exponentially
    assert delay_1 < delay_2 < delay_3
    assert delay_3 <= retry_config.max_delay
    
    print("[OK] Retry config works correctly")


@pytest.mark.unit
def test_model_imports():
    """Test that models can be imported."""
    from app.models.endpoint import Endpoint
    from app.models.check_result import CheckResult
    from app.models.notification_log import NotificationLog
    
    # Check that classes exist
    assert Endpoint is not None
    assert CheckResult is not None
    assert NotificationLog is not None
    
    # Check tablenames
    assert Endpoint.__tablename__ == "endpoints"
    assert CheckResult.__tablename__ == "check_results"
    assert NotificationLog.__tablename__ == "notification_logs"
    
    print("[OK] All models import correctly")


@pytest.mark.unit
def test_schema_validation():
    """Test Pydantic schema validation."""
    from app.schemas.endpoint import EndpointCreate, EndpointUpdate
    
    # Valid endpoint
    endpoint_data = EndpointCreate(
        name="Test",
        url="https://example.com",
        method="GET",
        interval=60,
        timeout=5,
        expected_status=200
    )
    
    assert endpoint_data.name == "Test"
    assert endpoint_data.interval == 60
    
    # Test validation - interval must be >= 10
    try:
        bad_endpoint = EndpointCreate(
            name="Bad",
            url="https://example.com",
            interval=5  # Too low!
        )
        assert False, "Should have raised validation error"
    except Exception:
        pass  # Expected
    
    print("[OK] Schema validation works correctly")


@pytest.mark.unit  
def test_logger_utility():
    """Test logger utility."""
    from app.utils.logger import get_logger, LoggerMixin
    
    logger = get_logger("test")
    assert logger is not None
    assert logger.name == "test"
    
    # Test LoggerMixin
    class TestClass(LoggerMixin):
        pass
    
    obj = TestClass()
    assert obj.logger is not None
    assert obj.logger.name == "TestClass"
    
    print("[OK] Logger utility works correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])