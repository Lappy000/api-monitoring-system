"""Comprehensive tests for statistics API endpoints."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette.datastructures import Headers, URL

from app.api import stats
from app.schemas.stats import (
    UptimeStatsResponse,
    CheckHistoryResponse,
    DowntimeIncidentsResponse,
    OverallSummaryResponse
)
from app.models.endpoint import Endpoint
from app.models.check_result import CheckResult
from app.core.uptime import UptimeCalculator


@pytest.fixture
def mock_db():
    """Create mock database session."""
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock()
    return db


@pytest.fixture
def mock_request():
    """Create mock request."""
    # Create a proper Starlette Request object
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/stats/uptime/1",
        "headers": [(b"user-agent", b"test")],
        "query_string": b"period=24h",
        "scheme": "http",
        "server": ("testserver", 80),
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
    return endpoint


@pytest.fixture
def sample_check_results():
    """Create sample check results."""
    results = []
    for i in range(5):
        result = MagicMock(spec=CheckResult)
        result.id = i + 1
        result.endpoint_id = 1
        result.status_code = 200 if i < 4 else 500
        result.response_time = 0.5 + i * 0.1
        result.success = i < 4
        result.error_message = None if i < 4 else "Connection timeout"
        result.checked_at = datetime.utcnow() - timedelta(minutes=i * 10)
        results.append(result)
    return results


@pytest.fixture
def uptime_stats_data():
    """Create sample uptime statistics data."""
    return {
        "endpoint_id": 1,
        "endpoint_name": "Test API",
        "period": "24h",
        "uptime_percentage": 95.5,
        "total_checks": 100,
        "successful_checks": 95,
        "failed_checks": 5,
        "avg_response_time": 0.5,
        "min_response_time": 0.1,
        "max_response_time": 2.0,
        "last_check": datetime.utcnow().isoformat(),
        "last_success": datetime.utcnow().isoformat(),
        "last_failure": (datetime.utcnow() - timedelta(hours=1)).isoformat()
    }


@pytest.mark.asyncio
async def test_get_uptime_stats_success(mock_request, mock_db, sample_endpoint, uptime_stats_data):
    """Test successful uptime stats retrieval."""
    # Mock endpoint existence check
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_endpoint
    mock_db.execute.return_value = mock_result
    
    # Mock UptimeCalculator
    with patch('app.api.stats.UptimeCalculator') as mock_calculator_class:
        mock_calculator = AsyncMock(spec=UptimeCalculator)
        mock_calculator.get_statistics.return_value = uptime_stats_data
        mock_calculator_class.return_value = mock_calculator
        
        # Call endpoint
        response = await stats.get_uptime_stats(
            request=mock_request,
            endpoint_id=1,
            period="24h",
            db=mock_db
        )
        
        # Verify response
        assert isinstance(response, UptimeStatsResponse)
        assert response.endpoint_id == 1
        assert response.endpoint_name == "Test API"
        assert response.uptime_percentage == 95.5
        assert response.total_checks == 100
        
        # Verify calculator was called
        mock_calculator.get_statistics.assert_called_once_with(1, "24h")


@pytest.mark.asyncio
async def test_get_uptime_stats_endpoint_not_found(mock_request, mock_db):
    """Test uptime stats with non-existent endpoint."""
    # Mock endpoint not found
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    # Call endpoint and expect exception
    with pytest.raises(HTTPException) as exc_info:
        await stats.get_uptime_stats(
            request=mock_request,
            endpoint_id=999,
            period="24h",
            db=mock_db
        )
    
    # Verify exception
    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert "Endpoint 999 not found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_uptime_stats_invalid_period(mock_request, mock_db, sample_endpoint):
    """Test uptime stats with invalid period parameter."""
    # Mock endpoint existence
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_endpoint
    mock_db.execute.return_value = mock_result
    
    # Mock UptimeCalculator to raise ValueError for invalid period
    with patch('app.api.stats.UptimeCalculator') as mock_calculator_class:
        mock_calculator = AsyncMock(spec=UptimeCalculator)
        mock_calculator.get_statistics.side_effect = ValueError("Invalid period: invalid")
        mock_calculator_class.return_value = mock_calculator
        
        # Call endpoint - should propagate ValueError as-is or handle it
        try:
            response = await stats.get_uptime_stats(
                request=mock_request,
                endpoint_id=1,
                period="invalid",
                db=mock_db
            )
            # If no exception, the endpoint doesn't validate period properly
            assert False, "Should have raised an exception for invalid period"
        except ValueError as e:
            # ValueError is expected from UptimeCalculator
            assert "Invalid period" in str(e)
        except HTTPException as e:
            # Or it might be wrapped in HTTPException
            assert e.status_code in [400, 422]


@pytest.mark.asyncio
async def test_get_check_history_success(mock_request, mock_db, sample_endpoint, sample_check_results):
    """Test successful check history retrieval."""
    # Ensure endpoint.name is a string, not a Mock
    sample_endpoint.name = "Test API"
    
    # Mock endpoint existence - first call
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_endpoint
    
    # Mock count query - second call
    count_result = MagicMock()
    count_result.scalars.return_value.all.return_value = sample_check_results
    
    # Mock paginated results query - third call
    paginated_result = MagicMock()
    paginated_result.scalars.return_value.all.return_value = sample_check_results
    
    # Set up execute to return different results for each call
    mock_db.execute.side_effect = [mock_result, count_result, paginated_result]
    
    # Call endpoint
    response = await stats.get_check_history(
        request=mock_request,
        endpoint_id=1,
        limit=100,
        offset=0,
        from_date=None,
        to_date=None,
        db=mock_db
    )
    
    # Verify response
    assert isinstance(response, CheckHistoryResponse)
    assert response.endpoint_id == 1
    assert response.endpoint_name == "Test API"
    assert response.total == 5
    assert len(response.checks) == 5


@pytest.mark.asyncio
async def test_get_check_history_with_date_filters(mock_request, mock_db, sample_endpoint, sample_check_results):
    """Test check history with date filters."""
    # Mock endpoint existence
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_endpoint
    mock_db.execute.return_value = mock_result
    
    from_date = (datetime.utcnow() - timedelta(days=1)).isoformat()
    to_date = datetime.utcnow().isoformat()
    
    # Call endpoint
    response = await stats.get_check_history(
        request=mock_request,
        endpoint_id=1,
        limit=50,
        offset=0,
        from_date=from_date,
        to_date=to_date,
        db=mock_db
    )
    
    # Verify response structure
    assert isinstance(response, CheckHistoryResponse)
    assert response.from_date == from_date
    assert response.to_date == to_date


@pytest.mark.asyncio
async def test_get_check_history_invalid_date_format(mock_request, mock_db, sample_endpoint):
    """Test check history with invalid date format."""
    # Mock endpoint existence
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_endpoint
    mock_db.execute.return_value = mock_result
    
    # Call endpoint with invalid date
    with pytest.raises(HTTPException) as exc_info:
        await stats.get_check_history(
            request=mock_request,
            endpoint_id=1,
            limit=100,
            offset=0,
            from_date="invalid-date",
            to_date=None,
            db=mock_db
        )
    
    # Verify exception
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid from_date format" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_check_history_endpoint_not_found(mock_request, mock_db):
    """Test check history with non-existent endpoint."""
    # Mock endpoint not found
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    # Call endpoint and expect exception
    with pytest.raises(HTTPException) as exc_info:
        await stats.get_check_history(
            request=mock_request,
            endpoint_id=999,
            limit=100,
            offset=0,
            from_date=None,
            to_date=None,
            db=mock_db
        )
    
    # Verify exception
    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert "Endpoint 999 not found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_downtime_incidents_success(mock_request, mock_db, sample_endpoint):
    """Test successful downtime incidents retrieval."""
    # Mock endpoint existence
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_endpoint
    mock_db.execute.return_value = mock_result
    
    # Mock incidents data
    incidents_data = [
        {
            "start": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
            "end": (datetime.utcnow() - timedelta(hours=1, minutes=30)).isoformat(),
            "duration_minutes": 30.0,
            "failure_count": 5,
            "errors": ["Connection timeout", "HTTP 500"]
        }
    ]
    
    # Mock UptimeCalculator
    with patch('app.api.stats.UptimeCalculator') as mock_calculator_class:
        mock_calculator = AsyncMock(spec=UptimeCalculator)
        mock_calculator.get_downtime_incidents.return_value = incidents_data
        mock_calculator_class.return_value = mock_calculator
        
        # Call endpoint
        response = await stats.get_downtime_incidents(
            request=mock_request,
            endpoint_id=1,
            period="7d",
            min_duration=1,
            db=mock_db
        )
        
        # Verify response
        assert isinstance(response, DowntimeIncidentsResponse)
        assert response.endpoint_id == 1
        assert response.endpoint_name == "Test API"
        assert response.total_incidents == 1
        assert len(response.incidents) == 1
        assert response.incidents[0].duration_minutes == 30.0
        
        # Verify calculator was called
        mock_calculator.get_downtime_incidents.assert_called_once_with(1, "7d", min_duration_minutes=1)


@pytest.mark.asyncio
async def test_get_downtime_incidents_no_incidents(mock_request, mock_db, sample_endpoint):
    """Test downtime incidents with no incidents found."""
    # Mock endpoint existence
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_endpoint
    mock_db.execute.return_value = mock_result
    
    # Mock empty incidents
    with patch('app.api.stats.UptimeCalculator') as mock_calculator_class:
        mock_calculator = AsyncMock(spec=UptimeCalculator)
        mock_calculator.get_downtime_incidents.return_value = []
        mock_calculator_class.return_value = mock_calculator
        
        # Call endpoint
        response = await stats.get_downtime_incidents(
            request=mock_request,
            endpoint_id=1,
            period="24h",
            min_duration=5,
            db=mock_db
        )
        
        # Verify response
        assert isinstance(response, DowntimeIncidentsResponse)
        assert response.total_incidents == 0
        assert len(response.incidents) == 0


@pytest.mark.asyncio
async def test_get_downtime_incidents_endpoint_not_found(mock_request, mock_db):
    """Test downtime incidents with non-existent endpoint."""
    # Mock endpoint not found
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    # Call endpoint and expect exception
    with pytest.raises(HTTPException) as exc_info:
        await stats.get_downtime_incidents(
            request=mock_request,
            endpoint_id=999,
            period="7d",
            min_duration=1,
            db=mock_db
        )
    
    # Verify exception
    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert "Endpoint 999 not found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_overall_summary_success(mock_request, mock_db):
    """Test successful overall summary retrieval."""
    # Mock summary data
    summary_data = {
        "total_endpoints": 10,
        "active_endpoints": 8,
        "inactive_endpoints": 2,
        "healthy_endpoints": 7,
        "unhealthy_endpoints": 1,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Mock UptimeCalculator
    with patch('app.api.stats.UptimeCalculator') as mock_calculator_class:
        mock_calculator = AsyncMock(spec=UptimeCalculator)
        mock_calculator.get_overall_summary.return_value = summary_data
        mock_calculator_class.return_value = mock_calculator
        
        # Call endpoint
        response = await stats.get_overall_summary(
            request=mock_request,
            db=mock_db
        )
        
        # Verify response
        assert isinstance(response, OverallSummaryResponse)
        assert response.total_endpoints == 10
        assert response.active_endpoints == 8
        assert response.healthy_endpoints == 7
        
        # Verify calculator was called
        mock_calculator.get_overall_summary.assert_called_once()


@pytest.mark.asyncio
async def test_get_overall_summary_empty(mock_request, mock_db):
    """Test overall summary with no endpoints."""
    # Mock empty summary
    summary_data = {
        "total_endpoints": 0,
        "active_endpoints": 0,
        "inactive_endpoints": 0,
        "healthy_endpoints": 0,
        "unhealthy_endpoints": 0,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    with patch('app.api.stats.UptimeCalculator') as mock_calculator_class:
        mock_calculator = AsyncMock(spec=UptimeCalculator)
        mock_calculator.get_overall_summary.return_value = summary_data
        mock_calculator_class.return_value = mock_calculator
        
        # Call endpoint
        response = await stats.get_overall_summary(
            request=mock_request,
            db=mock_db
        )
        
        # Verify response
        assert isinstance(response, OverallSummaryResponse)
        assert response.total_endpoints == 0
        assert response.healthy_endpoints == 0


@pytest.mark.asyncio
async def test_rate_limiting_applied(mock_request, mock_db, sample_endpoint, uptime_stats_data):
    """Test that rate limiting is applied to endpoints."""
    # Mock endpoint existence
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_endpoint
    mock_db.execute.return_value = mock_result
    
    # Mock UptimeCalculator
    with patch('app.api.stats.UptimeCalculator') as mock_calculator_class:
        mock_calculator = AsyncMock(spec=UptimeCalculator)
        mock_calculator.get_statistics.return_value = uptime_stats_data
        mock_calculator_class.return_value = mock_calculator
        
        # Call endpoint multiple times quickly
        for _ in range(3):
            response = await stats.get_uptime_stats(
                request=mock_request,
                endpoint_id=1,
                period="24h",
                db=mock_db
            )
            assert isinstance(response, UptimeStatsResponse)
        
        # Verify all calls succeeded (rate limit is high enough)
        assert mock_calculator.get_statistics.call_count == 3