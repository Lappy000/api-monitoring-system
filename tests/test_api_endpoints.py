"""API endpoint tests."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.endpoint import Endpoint


@pytest.mark.functional
class TestHealthEndpoint:
    """Test health check endpoint."""
    
    async def test_health_endpoint(self, test_app):
        """Test GET /health returns 200."""
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            response = await client.get("/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "version" in data
            assert "timestamp" in data


@pytest.mark.functional
class TestRootEndpoint:
    """Test root endpoint."""
    
    async def test_root_endpoint(self, test_app):
        """Test GET / returns API info."""
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            response = await client.get("/")
            
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "API Monitor"
            assert "version" in data
            assert data["status"] == "running"


@pytest.mark.functional
class TestEndpointsCRUD:
    """Test endpoint CRUD operations."""
    
    async def test_list_endpoints_empty(self, test_app):
        """Test listing endpoints when database is empty."""
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            response = await client.get("/api/v1/endpoints")
            
            assert response.status_code == 200
            data = response.json()
            assert "endpoints" in data
            assert "total" in data
            assert isinstance(data["endpoints"], list)
    
    async def test_create_endpoint(self, test_app):
        """Test creating a new endpoint."""
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            endpoint_data = {
                "name": "API Test Endpoint",
                "url": "https://httpbin.org/status/200",
                "method": "GET",
                "interval": 60,
                "timeout": 5,
                "expected_status": 200,
                "is_active": True
            }
            
            response = await client.post("/api/v1/endpoints", json=endpoint_data)
            
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == endpoint_data["name"]
            assert data["url"] == endpoint_data["url"]
            assert "id" in data
            assert "created_at" in data
    
    async def test_create_duplicate_endpoint_fails(self, test_app):
        """Test that creating duplicate endpoint fails."""
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            endpoint_data = {
                "name": "Duplicate Test",
                "url": "https://example.com",
                "method": "GET",
                "interval": 60,
                "timeout": 5,
                "expected_status": 200
            }
            
            # Create first
            response1 = await client.post("/api/v1/endpoints", json=endpoint_data)
            assert response1.status_code == 201
            
            # Try to create duplicate
            response2 = await client.post("/api/v1/endpoints", json=endpoint_data)
            assert response2.status_code == 400  # Bad request
    
    async def test_get_endpoint_by_id(self, test_app):
        """Test getting specific endpoint by ID."""
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            # Create endpoint first
            endpoint_data = {
                "name": "Get Test",
                "url": "https://example.com",
                "method": "GET",
                "interval": 60,
                "timeout": 5,
                "expected_status": 200
            }
            
            create_response = await client.post("/api/v1/endpoints", json=endpoint_data)
            assert create_response.status_code == 201
            endpoint_id = create_response.json()["id"]
            
            # Get endpoint
            get_response = await client.get(f"/api/v1/endpoints/{endpoint_id}")
            assert get_response.status_code == 200
            data = get_response.json()
            assert data["id"] == endpoint_id
            assert data["name"] == endpoint_data["name"]
    
    async def test_get_nonexistent_endpoint(self, test_app):
        """Test getting non-existent endpoint returns 404."""
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            response = await client.get("/api/v1/endpoints/99999")
            assert response.status_code == 404
    
    async def test_update_endpoint(self, test_app):
        """Test updating an endpoint."""
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            # Create endpoint
            endpoint_data = {
                "name": "Update Test",
                "url": "https://example.com",
                "method": "GET",
                "interval": 60,
                "timeout": 5,
                "expected_status": 200
            }
            
            create_response = await client.post("/api/v1/endpoints", json=endpoint_data)
            endpoint_id = create_response.json()["id"]
            
            # Update endpoint
            update_data = {
                "interval": 120,
                "is_active": False
            }
            
            update_response = await client.put(
                f"/api/v1/endpoints/{endpoint_id}",
                json=update_data
            )
            
            assert update_response.status_code == 200
            data = update_response.json()
            assert data["interval"] == 120
            assert data["is_active"] is False
    
    async def test_delete_endpoint(self, test_app):
        """Test deleting an endpoint."""
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            # Create endpoint
            endpoint_data = {
                "name": "Delete Test",
                "url": "https://example.com",
                "method": "GET",
                "interval": 60,
                "timeout": 5,
                "expected_status": 200
            }
            
            create_response = await client.post("/api/v1/endpoints", json=endpoint_data)
            endpoint_id = create_response.json()["id"]
            
            # Delete endpoint
            delete_response = await client.delete(f"/api/v1/endpoints/{endpoint_id}")
            assert delete_response.status_code == 204
            
            # Verify it's deleted
            get_response = await client.get(f"/api/v1/endpoints/{endpoint_id}")
            assert get_response.status_code == 404


@pytest.mark.functional
class TestStatsEndpoints:
    """Test statistics endpoints."""
    
    async def test_get_overall_summary(self, test_app):
        """Test getting overall summary."""
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            response = await client.get("/api/v1/stats/summary")
            
            assert response.status_code == 200
            data = response.json()
            assert "total_endpoints" in data
            assert "active_endpoints" in data
            assert "timestamp" in data
    
    async def test_get_uptime_stats_invalid_period(self, test_app):
        """Test that invalid period is rejected."""
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            # First create an endpoint
            endpoint_data = {
                "name": "Stats Test",
                "url": "https://example.com",
                "method": "GET",
                "interval": 60,
                "timeout": 5,
                "expected_status": 200
            }
            
            create_response = await client.post("/api/v1/endpoints", json=endpoint_data)
            endpoint_id = create_response.json()["id"]
            
            # Try invalid period
            response = await client.get(
                f"/api/v1/stats/uptime/{endpoint_id}?period=invalid"
            )
            
            # Should fail validation (422)
            assert response.status_code == 422


@pytest.mark.functional
class TestManualCheck:
    """Test manual endpoint checking."""
    
    async def test_trigger_manual_check(self, test_app):
        """Test triggering manual health check."""
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            # Create endpoint
            endpoint_data = {
                "name": "Manual Check Test",
                "url": "https://httpbin.org/status/200",
                "method": "GET",
                "interval": 60,
                "timeout": 5,
                "expected_status": 200
            }
            
            create_response = await client.post("/api/v1/endpoints", json=endpoint_data)
            endpoint_id = create_response.json()["id"]
            
            # Trigger manual check
            check_response = await client.post(f"/api/v1/endpoints/{endpoint_id}/check")
            
            assert check_response.status_code == 200
            data = check_response.json()
            assert "success" in data
            assert "checked_at" in data


@pytest.mark.functional
class TestAPIValidation:
    """Test API input validation."""
    
    async def test_create_endpoint_missing_required_fields(self, test_app):
        """Test that missing required fields are rejected."""
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            invalid_data = {
                "name": "Invalid Endpoint"
                # Missing url, method, etc.
            }
            
            response = await client.post("/api/v1/endpoints", json=invalid_data)
            assert response.status_code == 422  # Validation error
    
    async def test_create_endpoint_invalid_interval(self, test_app):
        """Test that invalid interval is rejected."""
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            invalid_data = {
                "name": "Invalid Interval",
                "url": "https://example.com",
                "method": "GET",
                "interval": 5,  # Less than minimum of 10
                "timeout": 5,
                "expected_status": 200
            }
            
            response = await client.post("/api/v1/endpoints", json=invalid_data)
            assert response.status_code == 422
    
    async def test_create_endpoint_invalid_status_code(self, test_app):
        """Test that invalid status code is rejected."""
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            invalid_data = {
                "name": "Invalid Status",
                "url": "https://example.com",
                "method": "GET",
                "interval": 60,
                "timeout": 5,
                "expected_status": 600  # Greater than max of 599
            }
            
            response = await client.post("/api/v1/endpoints", json=invalid_data)
            assert response.status_code == 422