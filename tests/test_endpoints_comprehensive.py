"""Comprehensive tests for endpoint management API."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.api import endpoints
from app.schemas.endpoint import (
    EndpointCreate,
    EndpointUpdate,
    EndpointResponse,
    EndpointListResponse,
    CheckManualRequest,
    CheckManualResponse
)
from app.models.endpoint import Endpoint
from app.models.check_result import CheckResult
from app.core.scheduler import MonitoringScheduler
from app.core.health_checker import HealthChecker


@pytest.fixture
def mock_db():
    """Create mock database session."""
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    return db


@pytest.fixture
def mock_request():
    """Create mock request."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/endpoints",
        "headers": [(b"user-agent", b"test")],
        "query_string": b"",
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 12345),
    }
    request = Request(scope)
    return request


@pytest.fixture
def sample_endpoint():
    """Create sample endpoint."""
    endpoint = MagicMock(spec=Endpoint)
    endpoint.id = 1
    endpoint.name = "Test API"
    endpoint.url = "https://api.example.com/health"
    endpoint.method = "GET"
    endpoint.interval = 60
    endpoint.timeout = 5
    endpoint.expected_status = 200
    endpoint.headers = {}
    endpoint.body = None
    endpoint.is_active = True
    endpoint.created_at = datetime.utcnow()
    endpoint.updated_at = datetime.utcnow()
    return endpoint


@pytest.fixture
def endpoint_create_data():
    """Create endpoint creation data."""
    return EndpointCreate(
        name="New API",
        url="https://new-api.com/health",
        method="GET",
        interval=60,
        timeout=5,
        expected_status=200,
        headers={},
        body=None,
        is_active=True
    )


@pytest.fixture
def endpoint_update_data():
    """Create endpoint update data."""
    return EndpointUpdate(
        name="Updated API",
        interval=120,
        is_active=False
    )


@pytest.mark.asyncio
async def test_list_endpoints_success(mock_request, mock_db, sample_endpoint):
    """Test successful endpoint listing."""
    # Mock query results
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [sample_endpoint]
    mock_db.execute.return_value = mock_result
    
    response = await endpoints.list_endpoints(
        request=mock_request,
        skip=0,
        limit=100,
        active_only=False,
        db=mock_db
    )
    
    assert isinstance(response, EndpointListResponse)
    assert len(response.endpoints) == 1
    assert response.total == 1


@pytest.mark.asyncio
async def test_list_endpoints_with_filters(mock_request, mock_db, sample_endpoint):
    """Test endpoint listing with active filter."""
    # Mock query results
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [sample_endpoint]
    mock_db.execute.return_value = mock_result
    
    response = await endpoints.list_endpoints(
        request=mock_request,
        skip=0,
        limit=50,
        active_only=True,
        db=mock_db
    )
    
    assert isinstance(response, EndpointListResponse)
    assert len(response.endpoints) == 1


@pytest.mark.asyncio
async def test_list_endpoints_pagination(mock_request, mock_db):
    """Test endpoint listing with pagination."""
    # Create multiple endpoints with proper attributes
    endpoints_list = []
    for i in range(3):
        ep = MagicMock(spec=Endpoint)
        ep.id = i + 1
        ep.name = f"API {i+1}"
        ep.url = f"https://api{i+1}.com"
        ep.method = "GET"
        ep.interval = 60
        ep.timeout = 5
        ep.expected_status = 200
        ep.headers = {}
        ep.body = None
        ep.is_active = True
        ep.created_at = datetime.utcnow()
        ep.updated_at = datetime.utcnow()
        endpoints_list.append(ep)
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = endpoints_list
    mock_db.execute.return_value = mock_result
    
    response = await endpoints.list_endpoints(
        request=mock_request,
        skip=0,
        limit=10,
        active_only=False,
        db=mock_db
    )
    
    assert response.total == 3
    assert len(response.endpoints) == 3


@pytest.mark.asyncio
async def test_create_endpoint_success(mock_request, mock_db, endpoint_create_data):
    """Test successful endpoint creation."""
    # Mock no existing endpoint
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    # Mock db.refresh to set id and timestamps
    def mock_refresh(obj):
        obj.id = 1
        obj.created_at = datetime.utcnow()
        obj.updated_at = datetime.utcnow()
    
    mock_db.refresh.side_effect = mock_refresh
    
    # Mock scheduler
    with patch('app.api.endpoints.get_scheduler') as mock_get_scheduler:
        mock_scheduler = AsyncMock(spec=MonitoringScheduler)
        mock_get_scheduler.return_value = mock_scheduler
        
        response = await endpoints.create_endpoint(
            request=mock_request,
            endpoint_data=endpoint_create_data,
            db=mock_db
        )
        
        # Verify endpoint was added
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        
        # Verify scheduler was called
        mock_scheduler.add_endpoint_job.assert_called_once()
        
        # Verify response
        assert isinstance(response, EndpointResponse)
        assert response.id == 1


@pytest.mark.asyncio
async def test_create_endpoint_duplicate_name(mock_request, mock_db, endpoint_create_data, sample_endpoint):
    """Test creating endpoint with duplicate name."""
    # Mock existing endpoint
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_endpoint
    mock_db.execute.return_value = mock_result
    
    with pytest.raises(HTTPException) as exc_info:
        await endpoints.create_endpoint(
            request=mock_request,
            endpoint_data=endpoint_create_data,
            db=mock_db
        )
    
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "already exists" in exc_info.value.detail


@pytest.mark.asyncio
async def test_create_endpoint_inactive_no_scheduler(mock_request, mock_db, endpoint_create_data):
    """Test creating inactive endpoint doesn't add to scheduler."""
    endpoint_create_data.is_active = False
    
    # Mock no existing endpoint
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    # Mock db.refresh to set id and timestamps
    def mock_refresh(obj):
        obj.id = 1
        obj.created_at = datetime.utcnow()
        obj.updated_at = datetime.utcnow()
    
    mock_db.refresh.side_effect = mock_refresh
    
    with patch('app.api.endpoints.get_scheduler') as mock_get_scheduler:
        mock_scheduler = AsyncMock(spec=MonitoringScheduler)
        mock_get_scheduler.return_value = mock_scheduler
        
        response = await endpoints.create_endpoint(
            request=mock_request,
            endpoint_data=endpoint_create_data,
            db=mock_db
        )
        
        # Scheduler should not be called for inactive endpoint
        mock_scheduler.add_endpoint_job.assert_not_called()
        
        # Verify endpoint was created
        assert isinstance(response, EndpointResponse)


@pytest.mark.asyncio
async def test_create_endpoint_no_scheduler(mock_request, mock_db, endpoint_create_data):
    """Test creating endpoint when scheduler is not available."""
    # Mock no existing endpoint
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    # Mock db.refresh to set id and timestamps
    def mock_refresh(obj):
        obj.id = 1
        obj.created_at = datetime.utcnow()
        obj.updated_at = datetime.utcnow()
    
    mock_db.refresh.side_effect = mock_refresh
    
    with patch('app.api.endpoints.get_scheduler') as mock_get_scheduler:
        mock_get_scheduler.return_value = None
        
        response = await endpoints.create_endpoint(
            request=mock_request,
            endpoint_data=endpoint_create_data,
            db=mock_db
        )
        
        # Should still succeed even without scheduler
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        
        # Verify response
        assert isinstance(response, EndpointResponse)
        assert response.id == 1


@pytest.mark.asyncio
async def test_get_endpoint_success(mock_request, mock_db, sample_endpoint):
    """Test getting endpoint by ID."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_endpoint
    mock_db.execute.return_value = mock_result
    
    response = await endpoints.get_endpoint(
        request=mock_request,
        endpoint_id=1,
        db=mock_db
    )
    
    assert isinstance(response, EndpointResponse)


@pytest.mark.asyncio
async def test_get_endpoint_not_found(mock_request, mock_db):
    """Test getting non-existent endpoint."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    with pytest.raises(HTTPException) as exc_info:
        await endpoints.get_endpoint(
            request=mock_request,
            endpoint_id=999,
            db=mock_db
        )
    
    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_update_endpoint_success(mock_request, mock_db, sample_endpoint, endpoint_update_data):
    """Test successful endpoint update."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_endpoint
    mock_db.execute.return_value = mock_result
    
    with patch('app.api.endpoints.get_scheduler') as mock_get_scheduler:
        mock_scheduler = AsyncMock(spec=MonitoringScheduler)
        mock_get_scheduler.return_value = mock_scheduler
        
        response = await endpoints.update_endpoint(
            request=mock_request,
            endpoint_id=1,
            endpoint_data=endpoint_update_data,
            db=mock_db
        )
        
        # Verify update
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        
        # Verify scheduler update
        mock_scheduler.update_endpoint_job.assert_called_once()


@pytest.mark.asyncio
async def test_update_endpoint_not_found(mock_request, mock_db, endpoint_update_data):
    """Test updating non-existent endpoint."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    with pytest.raises(HTTPException) as exc_info:
        await endpoints.update_endpoint(
            request=mock_request,
            endpoint_id=999,
            endpoint_data=endpoint_update_data,
            db=mock_db
        )
    
    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_update_endpoint_no_scheduler(mock_request, mock_db, sample_endpoint, endpoint_update_data):
    """Test updating endpoint when scheduler not available."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_endpoint
    mock_db.execute.return_value = mock_result
    
    with patch('app.api.endpoints.get_scheduler') as mock_get_scheduler:
        mock_get_scheduler.return_value = None
        
        response = await endpoints.update_endpoint(
            request=mock_request,
            endpoint_id=1,
            endpoint_data=endpoint_update_data,
            db=mock_db
        )
        
        # Should still succeed
        mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_delete_endpoint_success(mock_request, mock_db, sample_endpoint):
    """Test successful endpoint deletion."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_endpoint
    mock_db.execute.return_value = mock_result
    
    with patch('app.api.endpoints.get_scheduler') as mock_get_scheduler:
        mock_scheduler = AsyncMock(spec=MonitoringScheduler)
        mock_get_scheduler.return_value = mock_scheduler
        
        await endpoints.delete_endpoint(
            request=mock_request,
            endpoint_id=1,
            db=mock_db
        )
        
        # Verify deletion
        mock_db.delete.assert_called_once()
        mock_db.commit.assert_called_once()
        
        # Verify scheduler cleanup
        mock_scheduler.remove_endpoint_job.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_delete_endpoint_not_found(mock_request, mock_db):
    """Test deleting non-existent endpoint."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    with pytest.raises(HTTPException) as exc_info:
        await endpoints.delete_endpoint(
            request=mock_request,
            endpoint_id=999,
            db=mock_db
        )
    
    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_delete_endpoint_no_scheduler(mock_request, mock_db, sample_endpoint):
    """Test deleting endpoint when scheduler not available."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_endpoint
    mock_db.execute.return_value = mock_result
    
    with patch('app.api.endpoints.get_scheduler') as mock_get_scheduler:
        mock_get_scheduler.return_value = None
        
        await endpoints.delete_endpoint(
            request=mock_request,
            endpoint_id=1,
            db=mock_db
        )
        
        # Should still succeed
        mock_db.delete.assert_called_once()
        mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_manual_check_success(mock_request, mock_db, sample_endpoint):
    """Test successful manual check."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_endpoint
    mock_db.execute.return_value = mock_result
    
    # Mock check result
    check_result = MagicMock(spec=CheckResult)
    check_result.success = True
    check_result.status_code = 200
    check_result.response_time = 0.5
    check_result.error_message = None
    check_result.checked_at = datetime.utcnow()
    
    # Mock HealthChecker
    with patch('app.api.endpoints.HealthChecker') as mock_health_checker_class:
        mock_health_checker = AsyncMock(spec=HealthChecker)
        mock_health_checker.start = AsyncMock()
        mock_health_checker.close = AsyncMock()
        mock_health_checker.check_and_save = AsyncMock(return_value=check_result)
        mock_health_checker_class.return_value = mock_health_checker
        
        response = await endpoints.manual_check(
            request=mock_request,
            endpoint_id=1,
            check_request=CheckManualRequest(),
            db=mock_db
        )
        
        assert isinstance(response, CheckManualResponse)
        assert response.success is True
        assert response.status_code == 200
        
        # Verify health checker lifecycle
        mock_health_checker.start.assert_called_once()
        mock_health_checker.check_and_save.assert_called_once()
        mock_health_checker.close.assert_called_once()


@pytest.mark.asyncio
async def test_manual_check_endpoint_not_found(mock_request, mock_db):
    """Test manual check with non-existent endpoint."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    with pytest.raises(HTTPException) as exc_info:
        await endpoints.manual_check(
            request=mock_request,
            endpoint_id=999,
            check_request=CheckManualRequest(),
            db=mock_db
        )
    
    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_manual_check_failure(mock_request, mock_db, sample_endpoint):
    """Test manual check that fails."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_endpoint
    mock_db.execute.return_value = mock_result
    
    # Mock failed check result
    check_result = MagicMock(spec=CheckResult)
    check_result.success = False
    check_result.status_code = 500
    check_result.response_time = 2.5
    check_result.error_message = "Internal Server Error"
    check_result.checked_at = datetime.utcnow()
    
    with patch('app.api.endpoints.HealthChecker') as mock_health_checker_class:
        mock_health_checker = AsyncMock(spec=HealthChecker)
        mock_health_checker.start = AsyncMock()
        mock_health_checker.close = AsyncMock()
        mock_health_checker.check_and_save = AsyncMock(return_value=check_result)
        mock_health_checker_class.return_value = mock_health_checker
        
        response = await endpoints.manual_check(
            request=mock_request,
            endpoint_id=1,
            check_request=CheckManualRequest(),
            db=mock_db
        )
        
        assert isinstance(response, CheckManualResponse)
        assert response.success is False
        assert response.error_message == "Internal Server Error"


@pytest.mark.asyncio
async def test_manual_check_cleanup_on_error(mock_request, mock_db, sample_endpoint):
    """Test manual check cleans up health checker on error."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_endpoint
    mock_db.execute.return_value = mock_result
    
    with patch('app.api.endpoints.HealthChecker') as mock_health_checker_class:
        mock_health_checker = AsyncMock(spec=HealthChecker)
        mock_health_checker.start = AsyncMock()
        mock_health_checker.close = AsyncMock()
        mock_health_checker.check_and_save = AsyncMock(side_effect=Exception("Check failed"))
        mock_health_checker_class.return_value = mock_health_checker
        
        with pytest.raises(Exception):
            await endpoints.manual_check(
                request=mock_request,
                endpoint_id=1,
                check_request=CheckManualRequest(),
                db=mock_db
            )
        
        # Verify cleanup was called even on error
        mock_health_checker.close.assert_called_once()


@pytest.mark.asyncio
async def test_update_endpoint_partial(mock_request, mock_db, sample_endpoint):
    """Test partial endpoint update."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_endpoint
    mock_db.execute.return_value = mock_result
    
    # Partial update - only name
    partial_update = EndpointUpdate(name="Partially Updated")
    
    with patch('app.api.endpoints.get_scheduler') as mock_get_scheduler:
        mock_scheduler = AsyncMock(spec=MonitoringScheduler)
        mock_get_scheduler.return_value = mock_scheduler
        
        response = await endpoints.update_endpoint(
            request=mock_request,
            endpoint_id=1,
            endpoint_data=partial_update,
            db=mock_db
        )
        
        # Only name should be updated
        assert sample_endpoint.name == "Partially Updated"
        mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_list_endpoints_empty(mock_request, mock_db):
    """Test listing endpoints when none exist."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result
    
    response = await endpoints.list_endpoints(
        request=mock_request,
        skip=0,
        limit=100,
        active_only=False,
        db=mock_db
    )
    
    assert isinstance(response, EndpointListResponse)
    assert len(response.endpoints) == 0
    assert response.total == 0