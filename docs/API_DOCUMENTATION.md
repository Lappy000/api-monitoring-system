# API Monitoring System - API Documentation

## Overview

The API Monitoring System provides a comprehensive REST API for managing monitored endpoints, retrieving statistics, and configuring the monitoring system. All API endpoints follow RESTful principles and return JSON responses.

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

The API supports API key authentication. Include your API key in the request headers:

```
X-API-Key: your-api-key-here
```

## Rate Limiting

API endpoints are rate-limited to prevent abuse:
- **GET requests**: 100 requests per minute
- **POST requests**: 50 requests per minute

## Error Handling

The API uses conventional HTTP response codes to indicate success or failure:

- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `422` - Validation Error
- `429` - Too Many Requests
- `500` - Internal Server Error

Error responses include detailed information:

```json
{
  "detail": "Error description",
  "error": "Technical error details"
}
```

## Endpoints

### Health Check

#### `GET /health`

Check API health status.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-01-26T10:30:00Z",
  "database": "connected"
}
```

**Status Codes:**
- `200` - Service is healthy
- `503` - Service is unhealthy

---

### Endpoints Management

#### `GET /endpoints`

List all monitored endpoints.

**Query Parameters:**
- `skip` (integer, optional) - Number of records to skip (default: 0)
- `limit` (integer, optional) - Maximum records to return (default: 100, max: 1000)
- `active_only` (boolean, optional) - Show only active endpoints (default: false)

**Response:**
```json
{
  "endpoints": [
    {
      "id": 1,
      "name": "Production API",
      "url": "https://api.example.com/health",
      "method": "GET",
      "interval": 60,
      "timeout": 5,
      "expected_status": 200,
      "headers": {
        "Authorization": "Bearer token123"
      },
      "body": null,
      "is_active": true,
      "created_at": "2024-01-26T10:00:00Z",
      "updated_at": "2024-01-26T10:00:00Z"
    }
  ],
  "total": 1
}
```

**Status Codes:**
- `200` - Success
- `401` - Unauthorized
- `429` - Rate limit exceeded

---

#### `POST /endpoints`

Create a new monitoring endpoint.

**Request Body:**
```json
{
  "name": "Production API",
  "url": "https://api.example.com/health",
  "method": "GET",
  "interval": 60,
  "timeout": 5,
  "expected_status": 200,
  "headers": {
    "Authorization": "Bearer token123"
  },
  "body": null,
  "is_active": true
}
```

**Required Fields:**
- `name` - Unique endpoint name
- `url` - URL to monitor
- `method` - HTTP method (GET, POST, PUT, DELETE, PATCH)
- `interval` - Check interval in seconds (minimum: 10)
- `timeout` - Request timeout in seconds (minimum: 1)
- `expected_status` - Expected HTTP status code (1-599)

**Response:**
```json
{
  "id": 1,
  "name": "Production API",
  "url": "https://api.example.com/health",
  "method": "GET",
  "interval": 60,
  "timeout": 5,
  "expected_status": 200,
  "headers": {
    "Authorization": "Bearer token123"
  },
  "body": null,
  "is_active": true,
  "created_at": "2024-01-26T10:00:00Z",
  "updated_at": "2024-01-26T10:00:00Z"
}
```

**Status Codes:**
- `201` - Created successfully
- `400` - Endpoint with this name already exists
- `422` - Validation error
- `401` - Unauthorized
- `429` - Rate limit exceeded

---

#### `GET /endpoints/{id}`

Get a specific endpoint by ID.

**Response:**
```json
{
  "id": 1,
  "name": "Production API",
  "url": "https://api.example.com/health",
  "method": "GET",
  "interval": 60,
  "timeout": 5,
  "expected_status": 200,
  "headers": {
    "Authorization": "Bearer token123"
  },
  "body": null,
  "is_active": true,
  "created_at": "2024-01-26T10:00:00Z",
  "updated_at": "2024-01-26T10:00:00Z"
}
```

**Status Codes:**
- `200` - Success
- `404` - Endpoint not found
- `401` - Unauthorized

---

#### `PUT /endpoints/{id}`

Update an existing endpoint.

**Request Body:**
```json
{
  "name": "Updated API",
  "interval": 120,
  "is_active": false
}
```

**Response:**
```json
{
  "id": 1,
  "name": "Updated API",
  "url": "https://api.example.com/health",
  "method": "GET",
  "interval": 120,
  "timeout": 5,
  "expected_status": 200,
  "headers": {
    "Authorization": "Bearer token123"
  },
  "body": null,
  "is_active": false,
  "created_at": "2024-01-26T10:00:00Z",
  "updated_at": "2024-01-26T11:00:00Z"
}
```

**Status Codes:**
- `200` - Updated successfully
- `404` - Endpoint not found
- `422` - Validation error
- `401` - Unauthorized
- `429` - Rate limit exceeded

---

#### `DELETE /endpoints/{id}`

Delete an endpoint.

**Response:** `204 No Content`

**Status Codes:**
- `204` - Deleted successfully
- `404` - Endpoint not found
- `401` - Unauthorized
- `429` - Rate limit exceeded

---

#### `POST /endpoints/{id}/check`

Trigger a manual health check for an endpoint.

**Response:**
```json
{
  "endpoint_id": 1,
  "status_code": 200,
  "response_time": 0.234,
  "success": true,
  "error_message": null,
  "checked_at": "2024-01-26T10:30:00Z"
}
```

**Status Codes:**
- `200` - Check completed
- `404` - Endpoint not found
- `401` - Unauthorized
- `429` - Rate limit exceeded

---

### Statistics

#### `GET /stats/summary`

Get overall system summary.

**Response:**
```json
{
  "total_endpoints": 15,
  "active_endpoints": 12,
  "inactive_endpoints": 3,
  "total_checks_today": 1440,
  "failed_checks_today": 5,
  "average_uptime_24h": 99.65,
  "average_response_time": 0.245,
  "timestamp": "2024-01-26T10:30:00Z"
}
```

**Status Codes:**
- `200` - Success
- `401` - Unauthorized

---

#### `GET /stats/uptime/{endpoint_id}`

Get uptime statistics for a specific endpoint.

**Query Parameters:**
- `period` (string, required) - Time period: `24h`, `7d`, `30d`

**Response:**
```json
{
  "endpoint_id": 1,
  "endpoint_name": "Production API",
  "period": "7d",
  "uptime_percentage": 99.85,
  "total_checks": 1008,
  "successful_checks": 1007,
  "failed_checks": 1,
  "average_response_time": 0.234,
  "min_response_time": 0.120,
  "max_response_time": 0.580,
  "last_check": "2024-01-26T10:30:00Z"
}
```

**Status Codes:**
- `200` - Success
- `404` - Endpoint not found
- `422` - Invalid period parameter
- `401` - Unauthorized

---

#### `GET /stats/history/{endpoint_id}`

Get check history for an endpoint.

**Query Parameters:**
- `limit` (integer, optional) - Number of records to return (default: 100, max: 1000)
- `from_date` (string, optional) - Start date in ISO format
- `to_date` (string, optional) - End date in ISO format

**Response:**
```json
{
  "endpoint_id": 1,
  "endpoint_name": "Production API",
  "history": [
    {
      "id": 1001,
      "status_code": 200,
      "response_time": 0.234,
      "success": true,
      "error_message": null,
      "checked_at": "2024-01-26T10:30:00Z"
    },
    {
      "id": 1000,
      "status_code": 200,
      "response_time": 0.245,
      "success": true,
      "error_message": null,
      "checked_at": "2024-01-26T10:29:00Z"
    }
  ],
  "total": 2
}
```

**Status Codes:**
- `200` - Success
- `404` - Endpoint not found
- `401` - Unauthorized

---

### System Information

#### `GET /`

Get API information.

**Response:**
```json
{
  "name": "API Monitor",
  "version": "1.0.0",
  "status": "running",
  "docs": "/docs",
  "health": "/health"
}
```

**Status Codes:**
- `200` - Success

---

## WebSocket API (Future Enhancement)

Real-time updates will be available via WebSocket at:
```
ws://localhost:8000/ws
```

## Rate Limiting Headers

All API responses include rate limiting information:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1643205300
```

## Pagination

List endpoints support pagination:

```json
{
  "endpoints": [...],
  "total": 150,
  "skip": 0,
  "limit": 100
}
```

## Filtering and Sorting

### Available Filters
- `active_only` - Filter active/inactive endpoints
- `from_date` / `to_date` - Date range filtering

### Sorting
Results are sorted by creation date (newest first) by default.

## Examples

### Create an Endpoint

```bash
curl -X POST http://localhost:8000/api/v1/endpoints \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "name": "My API",
    "url": "https://api.example.com/health",
    "method": "GET",
    "interval": 60,
    "timeout": 5,
    "expected_status": 200
  }'
```

### Get Uptime Statistics

```bash
curl http://localhost:8000/api/v1/stats/uptime/1?period=7d \
  -H "X-API-Key: your-api-key"
```

### Trigger Manual Check

```bash
curl -X POST http://localhost:8000/api/v1/endpoints/1/check \
  -H "X-API-Key: your-api-key"
```

## SDKs and Client Libraries

### Python SDK
```python
from api_monitor import Client

client = Client(api_key="your-api-key", base_url="http://localhost:8000")

# Create endpoint
endpoint = client.endpoints.create(
    name="My API",
    url="https://api.example.com/health",
    interval=60
)

# Get uptime stats
stats = client.stats.get_uptime(endpoint_id=1, period="7d")
```

### JavaScript/TypeScript SDK
```javascript
import { ApiMonitorClient } from 'api-monitor-sdk';

const client = new ApiMonitorClient({
  apiKey: 'your-api-key',
  baseURL: 'http://localhost:8000'
});

// Create endpoint
const endpoint = await client.endpoints.create({
  name: 'My API',
  url: 'https://api.example.com/health',
  interval: 60
});

// Get uptime stats
const stats = await client.stats.getUptime(1, '7d');
```

## Support

For API support and questions:
- GitHub Issues: https://github.com/Lappy000/api-monitoring-system/issues
- Documentation: http://localhost:8000/docs
- Email: support@example.com

## Changelog

### Version 1.0.0
- Initial API release
- Endpoint management
- Health check monitoring
- Statistics and reporting
- Notification system
- Rate limiting
- API authentication

---

**Last Updated:** January 26, 2024  
**API Version:** 1.0.0  
**Documentation Version:** 1.0.0