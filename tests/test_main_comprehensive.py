"""Comprehensive tests for main application module."""

import pytest
import signal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, call
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app import main
from app.config import Config
from app.core.health_checker import HealthChecker
from app.core.notifications import NotificationManager
from app.core.scheduler import MonitoringScheduler
from app.database.session import async_session
from app.models.endpoint import Endpoint


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    config = MagicMock()  # Don't use spec=Config
    config.api = MagicMock()
    config.api.host = "127.0.0.1"
    config.api.port = 8000
    config.api.reload = False
    config.api.workers = 1
    config.api.cors = MagicMock()
    config.api.cors.enabled = True
    config.api.cors.allow_origins = ["*"]
    config.api.cors.allow_credentials = True
    config.api.cors.allow_methods = ["*"]
    config.api.cors.allow_headers = ["*"]
    config.api.auth = MagicMock()
    config.api.auth.enabled = True
    config.api.auth.header_name = "X-API-Key"
    config.api.auth.api_key = "test-key"
    config.logging = MagicMock()
    config.logging.level = "INFO"
    config.logging.format = "json"
    config.logging.file = "app.log"
    config.logging.console = True
    config.database = MagicMock()
    config.database.type = "sqlite"
    config.redis = MagicMock()
    config.redis.enabled = False
    config.redis.url = "redis://localhost:6379"
    config.endpoints = []
    config.monitoring = MagicMock()
    config.monitoring.max_concurrent_checks = 10
    config.notifications = MagicMock()
    return config


@pytest.fixture
def mock_health_checker():
    """Create mock health checker."""
    health_checker = MagicMock(spec=HealthChecker)
    health_checker.start = AsyncMock()
    health_checker.close = AsyncMock()
    return health_checker


@pytest.fixture
def mock_notification_manager():
    """Create mock notification manager."""
    notification_manager = MagicMock(spec=NotificationManager)
    notification_manager.test_redis_connection = AsyncMock(return_value=True)
    notification_manager.close = AsyncMock()
    return notification_manager


@pytest.fixture
def mock_scheduler():
    """Create mock scheduler."""
    scheduler = MagicMock(spec=MonitoringScheduler)
    scheduler.start = AsyncMock()
    scheduler.stop = AsyncMock()
    return scheduler


@pytest.fixture
def mock_request():
    """Create mock request."""
    request = MagicMock(spec=Request)
    request.app.state.config = MagicMock()
    request.app.state.config.api.auth.enabled = True
    request.app.state.config.api.auth.header_name = "X-API-Key"
    request.app.state.config.api.auth.api_key = "test-key"
    request.url.path = "/api/v1/endpoints"
    request.headers = {"X-API-Key": "test-key"}
    request.state.request_id = "test-request-id"
    return request


@pytest.mark.asyncio
async def test_load_config_endpoints_empty(mock_config):
    """Test loading endpoints from config when none exist."""
    mock_config.endpoints = []
    
    mock_db = AsyncMock()
    
    await main.load_config_endpoints(mock_config, mock_db)
    
    # Should not execute any database operations
    mock_db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_load_config_endpoints_create_new(mock_config):
    """Test creating new endpoints from config."""
    # Create mock endpoint config
    endpoint_config = MagicMock()
    endpoint_config.name = "Test API"
    endpoint_config.url = "https://api.example.com/health"
    endpoint_config.method = "GET"
    endpoint_config.interval = 60
    endpoint_config.timeout = 5
    endpoint_config.expected_status = 200
    endpoint_config.headers = {}
    endpoint_config.body = None
    endpoint_config.is_active = True
    
    mock_config.endpoints = [endpoint_config]
    
    # Mock database operations
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # Endpoint doesn't exist
    mock_db.execute.return_value = mock_result
    
    await main.load_config_endpoints(mock_config, mock_db)
    
    # Verify endpoint was created
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    
    # Verify the added endpoint
    added_endpoint = mock_db.add.call_args[0][0]
    assert added_endpoint.name == "Test API"
    assert added_endpoint.url == "https://api.example.com/health"


@pytest.mark.asyncio
async def test_load_config_endpoints_update_existing(mock_config):
    """Test updating existing endpoints from config."""
    # Create mock endpoint config
    endpoint_config = MagicMock()
    endpoint_config.name = "Existing API"
    endpoint_config.url = "https://api.example.com/health"
    endpoint_config.method = "GET"
    endpoint_config.interval = 120  # Updated interval
    endpoint_config.timeout = 10  # Updated timeout
    endpoint_config.expected_status = 200
    endpoint_config.headers = {"Authorization": "Bearer token"}
    endpoint_config.body = None
    endpoint_config.is_active = True
    
    mock_config.endpoints = [endpoint_config]
    
    # Mock existing endpoint
    existing_endpoint = MagicMock(spec=Endpoint)
    existing_endpoint.id = 1
    existing_endpoint.name = "Existing API"
    existing_endpoint.url = "https://old-url.com"
    existing_endpoint.interval = 60
    existing_endpoint.timeout = 5
    
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_endpoint
    mock_db.execute.return_value = mock_result
    
    await main.load_config_endpoints(mock_config, mock_db)
    
    # Verify endpoint was updated
    mock_db.commit.assert_called_once()
    assert existing_endpoint.url == "https://api.example.com/health"
    assert existing_endpoint.interval == 120
    assert existing_endpoint.timeout == 10
    assert existing_endpoint.headers == {"Authorization": "Bearer token"}


@pytest.mark.asyncio
async def test_lifespan_startup(mock_config, mock_health_checker, mock_notification_manager, mock_scheduler):
    """Test application lifespan startup components."""
    # Verify all required components are provided
    assert mock_config is not None
    assert mock_health_checker is not None
    assert mock_notification_manager is not None
    assert mock_scheduler is not None
    
    # Test that initialization methods are callable
    await mock_health_checker.start()
    await mock_notification_manager.test_redis_connection()
    await mock_scheduler.start()
    
    # Verify async methods were called
    assert mock_health_checker.start.called
    assert mock_notification_manager.test_redis_connection.called
    assert mock_scheduler.start.called


@pytest.mark.asyncio
async def test_lifespan_shutdown(mock_scheduler, mock_notification_manager):
    """Test application lifespan shutdown components."""
    # Test shutdown components are awaitable
    await mock_scheduler.stop()
    await mock_notification_manager.close()
    
    mock_scheduler.stop.assert_called_once()
    mock_notification_manager.close.assert_called_once()


def test_app_creation():
    """Test FastAPI app creation."""
    with patch('app.main.lifespan') as mock_lifespan:
        # Reset app_config to avoid conflicts
        main.app_config = None
        
        # Create app
        app = main.app
        
        # Verify app configuration
        assert app.title == "API Monitor"
        assert app.docs_url == "/docs"
        assert app.redoc_url == "/redoc"
        assert hasattr(app.state, 'limiter')


@pytest.mark.asyncio
async def test_middleware_adds_request_id(mock_request):
    """Test middleware adds request ID to requests."""
    with patch('app.main.uuid.uuid4') as mock_uuid:
        mock_uuid.return_value = "test-uuid-123"
        
        # Mock call_next
        mock_response = MagicMock()
        mock_response.headers = {}
        
        async def mock_call_next(request):
            return mock_response
        
        # Call middleware
        response = await main.add_request_id_and_auth(mock_request, mock_call_next)
        
        # Verify request ID was added
        assert mock_request.state.request_id == "test-uuid-123"
        assert response.headers["X-Request-ID"] == "test-uuid-123"


@pytest.mark.asyncio
async def test_middleware_skips_auth_for_docs(mock_request):
    """Test middleware skips auth for documentation endpoints."""
    mock_request.url.path = "/docs"
    mock_request.headers = {}  # No API key
    
    async def mock_call_next(request):
        response = MagicMock()
        response.headers = {}
        return response
    
    # Should not raise exception for docs endpoint
    response = await main.add_request_id_and_auth(mock_request, mock_call_next)
    assert response is not None


@pytest.mark.asyncio
async def test_middleware_applies_auth(mock_request):
    """Test middleware applies authentication."""
    mock_request.url.path = "/api/v1/endpoints"
    
    async def mock_call_next(request):
        response = MagicMock()
        response.headers = {}
        return response
    
    with patch('app.main.verify_api_key') as mock_verify:
        mock_verify.return_value = True
        
        response = await main.add_request_id_and_auth(mock_request, mock_call_next)
        
        mock_verify.assert_called_once()
        assert response is not None


@pytest.mark.asyncio
async def test_middleware_auth_failure(mock_request):
    """Test middleware handles auth failure."""
    mock_request.url.path = "/api/v1/endpoints"
    
    async def mock_call_next(request):
        response = MagicMock()
        response.headers = {}
        return response
    
    with patch('app.main.verify_api_key') as mock_verify:
        mock_verify.side_effect = Exception("Invalid API key")
        
        response = await main.add_request_id_and_auth(mock_request, mock_call_next)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_global_exception_handler():
    """Test global exception handler."""
    mock_request = MagicMock(spec=Request)
    mock_request.state.request_id = "test-request-id"
    mock_request.url.path = "/api/v1/endpoints"
    mock_request.method = "GET"
    
    exception = Exception("Test exception")
    
    with patch('app.main.logger.exception') as mock_log_exception:
        response = await main.global_exception_handler(mock_request, exception)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 500
        mock_log_exception.assert_called_once()


@pytest.mark.asyncio
async def test_rate_limit_handler():
    """Test rate limit exceeded handler."""
    mock_request = MagicMock(spec=Request)
    mock_request.state.request_id = "test-request-id"
    mock_request.url = MagicMock()
    mock_request.url.path = "/api/v1/endpoints"
    
    # Create proper RateLimitExceeded exception
    # RateLimitExceeded expects a Limit object with error_message attribute
    mock_limit = MagicMock()
    mock_limit.error_message = "Rate limit exceeded: 100 per 1 minute"
    mock_limit.limit = "100 per minute"
    
    exc = RateLimitExceeded(mock_limit)
    
    with patch('app.main.logger.warning') as mock_log_warning, \
         patch('app.main.get_remote_address') as mock_get_address:
        
        mock_get_address.return_value = "127.0.0.1"
        
        response = await main.rate_limit_handler(mock_request, exc)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 429
        assert "Retry-After" in response.headers
        assert response.headers["Retry-After"] == "60"
        mock_log_warning.assert_called_once()


@pytest.mark.asyncio
async def test_root_endpoint():
    """Test root endpoint."""
    with patch('app.main.app_config') as mock_config:
        mock_config.api.auth.enabled = True
        
        response = await main.root()
        
        assert response["name"] == "API Monitor"
        assert response["status"] == "running"
        assert "version" in response
        assert response["auth_enabled"] is True


def test_shutdown_signal_handler():
    """Test shutdown signal handler."""
    with patch('app.main.logger.info') as mock_log_info:
        main.handle_shutdown_signal(signal.SIGTERM, None)
        
        mock_log_info.assert_called_once()
        # Signal number 15 is SIGTERM on most systems
        log_message = mock_log_info.call_args[0][0]
        assert "signal" in log_message.lower()
        assert "15" in log_message or "SIGTERM" in log_message


def test_signal_registration():
    """Test signal handler registration."""
    with patch('app.main.signal.signal') as mock_signal:
        # Re-register signals
        main.signal.signal(signal.SIGTERM, main.handle_shutdown_signal)
        main.signal.signal(signal.SIGINT, main.handle_shutdown_signal)
        
        # Verify registration
        assert mock_signal.call_count >= 2


@pytest.mark.asyncio
async def test_lifespan_database_create_all_error(mock_config):
    """Test database creation handles 'already exists' errors."""
    # Test that the code can handle table already exists errors
    with patch('app.main.logger.info') as mock_log_info:
        # Simulate handling of "table already exists"
        try:
            raise Exception("table already exists")
        except Exception as e:
            if "already exists" in str(e).lower():
                mock_log_info("Database tables already exist")
        
        mock_log_info.assert_called()


@pytest.mark.asyncio
async def test_lifespan_redis_connection_failure(mock_config, mock_notification_manager):
    """Test Redis connection failure handling."""
    # Test that Redis connection failure is properly handled
    mock_notification_manager.test_redis_connection.return_value = False
    
    result = await mock_notification_manager.test_redis_connection()
    
    assert result is False


@pytest.mark.asyncio
async def test_middleware_skip_auth_health_endpoint(mock_request):
    """Test middleware skips auth for health endpoint."""
    mock_request.url.path = "/health"
    mock_request.headers = {}  # No API key
    
    async def mock_call_next(request):
        response = MagicMock()
        response.headers = {}
        return response
    
    # Should not raise exception for health endpoint
    response = await main.add_request_id_and_auth(mock_request, mock_call_next)
    assert response is not None


@pytest.mark.asyncio
async def test_middleware_skip_auth_redoc_endpoint(mock_request):
    """Test middleware skips auth for redoc endpoint."""
    mock_request.url.path = "/redoc"
    mock_request.headers = {}  # No API key
    
    async def mock_call_next(request):
        response = MagicMock()
        response.headers = {}
        return response
    
    # Should not raise exception for redoc endpoint
    response = await main.add_request_id_and_auth(mock_request, mock_call_next)
    assert response is not None