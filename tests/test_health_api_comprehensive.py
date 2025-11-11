"""Comprehensive tests for health API endpoints."""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from fastapi import status as http_status

from app.api.health import health_check, circuit_breaker_status
from app import __version__


@pytest.mark.asyncio
async def test_health_check_with_scheduler():
    """Test health check when scheduler is running."""
    mock_scheduler = MagicMock()
    
    with patch('app.api.health.get_scheduler', return_value=mock_scheduler):
        response = await health_check()
        
        assert response.status == "healthy"
        assert response.version == __version__
        assert response.database == "connected"
        assert response.scheduler == "running"
        assert response.timestamp is not None


@pytest.mark.asyncio
async def test_health_check_no_scheduler():
    """Test health check when scheduler is stopped."""
    with patch('app.api.health.get_scheduler', return_value=None):
        response = await health_check()
        
        assert response.status == "healthy"
        assert response.version == __version__
        assert response.database == "connected"
        assert response.scheduler == "stopped"


@pytest.mark.asyncio
async def test_circuit_breaker_status_empty():
    """Test circuit breaker status with no breakers."""
    mock_registry = MagicMock()
    mock_registry.get_all_states.return_value = {}
    
    with patch('app.api.health.circuit_breaker_registry', mock_registry):
        response = await circuit_breaker_status()
        
        # Response is JSONResponse, get the body
        assert response.status_code == 200
        body = response.body.decode()
        
        # Verify it contains summary
        assert "summary" in body
        assert "total_circuit_breakers" in body


@pytest.mark.asyncio
async def test_circuit_breaker_status_with_breakers():
    """Test circuit breaker status with multiple breakers."""
    mock_registry = MagicMock()
    mock_registry.get_all_states.return_value = {
        "breaker1": {"state": "closed", "failure_count": 0},
        "breaker2": {"state": "open", "failure_count": 5},
        "breaker3": {"state": "half_open", "failure_count": 2}
    }
    
    with patch('app.api.health.circuit_breaker_registry', mock_registry):
        response = await circuit_breaker_status()
        
        assert response.status_code == 200
        body = response.body.decode()
        
        # Verify summary counts
        assert "open" in body
        assert "half_open" in body
        assert "closed" in body


@pytest.mark.asyncio
async def test_circuit_breaker_status_all_closed():
    """Test circuit breaker status with all closed."""
    mock_registry = MagicMock()
    mock_registry.get_all_states.return_value = {
        "breaker1": {"state": "closed", "failure_count": 0},
        "breaker2": {"state": "closed", "failure_count": 0}
    }
    
    with patch('app.api.health.circuit_breaker_registry', mock_registry):
        response = await circuit_breaker_status()
        
        assert response.status_code == 200
        body = response.body.decode()
        
        # All should be closed
        assert "closed" in body


@pytest.mark.asyncio
async def test_circuit_breaker_status_all_open():
    """Test circuit breaker status with all open."""
    mock_registry = MagicMock()
    mock_registry.get_all_states.return_value = {
        "breaker1": {"state": "open", "failure_count": 5},
        "breaker2": {"state": "open", "failure_count": 5}
    }
    
    with patch('app.api.health.circuit_breaker_registry', mock_registry):
        response = await circuit_breaker_status()
        
        assert response.status_code == 200
        body = response.body.decode()
        
        # Check for open count
        assert "open" in body