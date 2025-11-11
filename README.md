# API Monitoring System

A production-ready API monitoring system with asynchronous health checks, persistent storage, uptime analytics, and multi-channel notifications.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

### Core Functionality
- **Asynchronous Health Checks**: Monitor 50+ endpoints concurrently without blocking
- **Flexible Scheduling**: Configure different check intervals per endpoint
- **Persistent Storage**: SQLite for development, PostgreSQL for production
- **Uptime Analytics**: Calculate uptime for 24h, 7d, and 30d periods
- **Multi-Channel Notifications**: Email, Webhooks, and Telegram support
- **RESTful API**: Full CRUD operations and statistics endpoints
- **YAML Configuration**: Simple, readable configuration files

### Technical Features
- **Async I/O**: Built with `asyncio` for maximum performance
- **Retry Mechanism**: Exponential backoff for transient failures
- **Structured Logging**: JSON and text formats with rotation
- **Comprehensive Tests**: Extensive test coverage with pytest
- **Docker Support**: Ready-to-deploy containers
- **Type Safety**: Full type hints with mypy validation
- **Graceful Shutdown**: Proper cleanup of resources
- **Database Migrations**: Alembic for schema versioning

## Requirements

- Python 3.11+
- SQLite 3.x (included) or PostgreSQL 12+
- 512MB RAM minimum
- Linux, macOS, or Windows

## Quick Start

### 1. Installation

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/api-monitoring-system
cd api-monitoring-system

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy example configuration
cp config/config.yaml.example config/config.yaml
cp .env.example .env

# Edit configuration
nano config/config.yaml
```

**Minimal Configuration:**
```yaml
database:
  type: "sqlite"
  url: "sqlite:///./data/api_monitor.db"

endpoints:
  - name: "Example API"
    url: "https://api.github.com/status"
    method: "GET"
    interval: 60
    timeout: 5
    expected_status: 200

notifications:
  enabled: false
```

### 3. Initialize Database

```bash
# Run migrations
alembic upgrade head
```

### 4. Start Server

```bash
# Development
uvicorn app.main:app --reload

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Visit: http://localhost:8000/docs for API documentation

## Docker Deployment

### Using Docker Compose (Recommended)

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f api-monitor

# Stop
docker-compose down
```

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  api-monitor:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://monitor:secret@postgres:5432/api_monitor
      - CONFIG_PATH=/app/config/config.yaml
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
    depends_on:
      - postgres
    restart: unless-stopped
    
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: api_monitor
      POSTGRES_USER: monitor
      POSTGRES_PASSWORD: secret
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  postgres_data:
```

### Using Docker Only

```bash
# Build image
docker build -t api-monitor .

# Run container
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/logs:/app/logs \
  --name api-monitor \
  api-monitor
```

## Configuration Guide

### Endpoint Configuration

```yaml
endpoints:
  - name: "Service Name"
    url: "https://api.example.com/health"
    method: "GET"  # GET, POST, PUT, DELETE, PATCH
    interval: 60  # seconds
    timeout: 5  # seconds
    expected_status: 200
    headers:  # optional
      Authorization: "Bearer token"
    body:  # optional, for POST requests
      ping: "test"
    is_active: true
```

### Notification Configuration

#### Email
```yaml
notifications:
  email:
    enabled: true
    smtp_host: "smtp.gmail.com"
    smtp_port: 587
    smtp_user: "your-email@gmail.com"
    smtp_password: "app-password"
    from_addr: "monitor@example.com"
    to_addrs:
      - "admin@example.com"
```

#### Webhook (Slack Example)
```yaml
notifications:
  webhook:
    enabled: true
    url: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
    retry_count: 3
    payload_template: |
      {
        "text": "*{endpoint_name}* is DOWN\nError: {error}"
      }
```

## API Documentation

### Endpoints

#### Health Check
```bash
GET /health
```

#### List Endpoints
```bash
GET /api/v1/endpoints
```

Response:
```json
{
  "endpoints": [
    {
      "id": 1,
      "name": "Production API",
      "url": "https://api.example.com/health",
      "method": "GET",
      "interval": 60,
      "is_active": true,
      "created_at": "2024-01-26T10:00:00Z"
    }
  ],
  "total": 1
}
```

#### Create Endpoint
```bash
POST /api/v1/endpoints
Content-Type: application/json

{
  "name": "New Service",
  "url": "https://api.example.com/status",
  "method": "GET",
  "interval": 120,
  "timeout": 10,
  "expected_status": 200
}
```

#### Get Uptime Statistics
```bash
GET /api/v1/stats/uptime/1?period=7d
```

Response:
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
  "last_check": "2024-01-26T10:30:00Z"
}
```

#### Get Check History
```bash
GET /api/v1/stats/history/1?limit=100&from_date=2024-01-25
```

#### Trigger Manual Check
```bash
POST /api/v1/endpoints/1/check
```

### API Authentication

Enable in `config.yaml`:
```yaml
api:
  auth:
    enabled: true
    api_key: "your-secret-key"
```

Use in requests:
```bash
curl -H "X-API-Key: your-secret-key" http://localhost:8000/api/v1/endpoints
```

## Monitoring & Analytics

The system provides comprehensive statistics through the REST API:
- Uptime percentages (24h, 7d, 30d periods)
- Response time metrics (min, max, average)
- Check history with timestamps
- Downtime incident tracking
- Overall system health summary

## Testing

### 🎯 Quick Test (Recommended for Users)

```bash
# Automatic verification (checks everything)
python verify_tests.py
```

This script will:
- ✅ Check all dependencies are installed
- ✅ Run smoke tests (2 seconds)
- ✅ Verify code coverage ≥80%
- ✅ Show final status

**⚠️ IMPORTANT:** Don't run `pytest` without parameters! This project has legacy tests that conflict with new comprehensive tests. Use the scripts above instead.

### 📊 Detailed Test Reports

```bash
# Windows users
test.bat           # Full test suite
test.bat quick     # Fast smoke tests
test.bat html      # HTML coverage report

# Linux/Mac users
python run_tests.py          # Full test suite
python run_tests.py --quick  # Fast smoke tests
python run_tests.py --html   # HTML coverage report
```

### 🔧 For Developers

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run ONLY comprehensive tests (recommended)
pytest tests/test_*_comprehensive.py --cov=app --cov-report=html

# Run specific module tests
python run_tests.py --module auth
python run_tests.py --module endpoints

# Type checking
mypy app/

# Code formatting
black app/ tests/

# Linting
flake8 app/ tests/
```

### 📖 Test Documentation

For detailed testing guide, see:
- **[README_TESTING.md](README_TESTING.md)** - Complete testing guide for users
- **[tests/README.md](tests/README.md)** - Technical documentation for developers
- **[TESTING_GUIDE.md](TESTING_GUIDE.md)** - Quick start guide


### Project Structure

```
api-monitor/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration management
│   ├── core/                # Core business logic
│   │   ├── health_checker.py
│   │   ├── scheduler.py
│   │   ├── notifications.py
│   │   └── uptime.py
│   ├── models/              # Database models
│   ├── schemas/             # Pydantic schemas
│   ├── api/                 # API routes
│   └── utils/               # Utilities
├── tests/                   # Test suite
├── config/                  # Configuration files
├── alembic/                 # Database migrations
└── docs/                    # Documentation
```

## Security Best Practices

1. **Never commit secrets**: Use `.env` files for sensitive data
2. **Use environment variables**: Override config with env vars in production
3. **Enable API authentication**: Protect endpoints with API keys
4. **Use HTTPS**: Always use TLS in production
5. **Rotate credentials**: Regularly update passwords and API keys
6. **Limit permissions**: Use read-only database users where possible
7. **Rate limiting**: Enable rate limiting in production
8. **Input validation**: Pydantic handles validation automatically

## Performance Optimization

### For 50+ Endpoints

1. **Use PostgreSQL**: Better performance than SQLite for concurrent writes
2. **Adjust pool size**: Increase database connection pool
   ```yaml
   database:
     pool_size: 20
     max_overflow: 30
   ```
3. **Optimize intervals**: Don't check all endpoints at the same time
4. **Enable caching**: Cache uptime calculations
5. **Use indexes**: Ensure proper database indexes
6. **Monitor resources**: Track CPU, memory, and database performance

### Recommended Settings

```yaml
monitoring:
  max_concurrent_checks: 50
  check_history_days: 30  # Reduce if needed

database:
  pool_size: 20
  echo: false

api:
  workers: 4  # CPU cores
```

## Troubleshooting

### Common Issues

#### 1. Database Connection Errors

**SQLite locked:**
```
sqlite3.OperationalError: database is locked
```
Solution: Use PostgreSQL for production or reduce concurrent checks

**PostgreSQL connection refused:**
```
psycopg2.OperationalError: could not connect to server
```
Solution: Check PostgreSQL is running and connection string is correct

#### 2. Notification Failures

**Email not sending:**
- Check SMTP credentials
- Use app-specific password for Gmail
- Verify firewall allows SMTP port

**Webhook timeout:**
- Increase webhook timeout in config
- Check webhook URL is accessible
- Verify payload format

#### 3. Performance Issues

**Slow checks:**
- Reduce `max_concurrent_checks`
- Increase endpoint timeouts
- Check network connectivity

**High memory usage:**
- Reduce `check_history_days`
- Enable periodic cleanup
- Optimize database queries

### Debug Mode

Enable debug logging:
```yaml
logging:
  level: "DEBUG"
  format: "text"
```

Or with environment variable:
```bash
LOG_LEVEL=DEBUG uvicorn app.main:app
```

### Health Check

```bash
# Check API health
curl http://localhost:8000/health

# Check database connection
curl http://localhost:8000/api/v1/stats/summary

# View logs
tail -f logs/api_monitor.log
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Run tests: `pytest`
5. Commit: `git commit -m 'Add amazing feature'`
6. Push: `git push origin feature/amazing-feature`
7. Open a Pull Request

### Code Style

- Follow PEP 8
- Use Black for formatting
- Add type hints to all functions
- Write docstrings for public methods
- Maintain >80% test coverage

## License

This project is licensed under the MIT License - see LICENSE file for details.

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Async HTTP with [aiohttp](https://docs.aiohttp.org/)
- Scheduling with [APScheduler](https://apscheduler.readthedocs.io/)
- Database with [SQLAlchemy](https://www.sqlalchemy.org/)

## Roadmap

### Planned Features
- Web Dashboard: Visual interface for monitoring status and statistics
- Prometheus Metrics: Export metrics for Prometheus/Grafana integration
- Mobile App: Push notifications for critical alerts
- Multi-Region Monitoring: Distributed health checks from multiple locations
- Custom Assertions: Validate response body content beyond status codes
- SLA Tracking: Service Level Agreement monitoring and reporting
- APM Integration: Connect with tools like DataDog, New Relic
- GraphQL API: Alternative API interface
- WebSocket Updates: Real-time status updates for dashboards
- Response Body Validation: JSON schema validation for API responses

### ✅ Completed
- **Test Coverage**: Improved from 63% to 80% with comprehensive test suite
- **Event Loop Stability**: Resolved async test conflicts for 100% success rate
- **Test Documentation**: Created user-friendly guides and automated verification

### In Progress
- **Performance**: Load testing for 50+ endpoints
- **Notifications**: Integration testing for delivery verification

### Planned
- **Prometheus Metrics**: For advanced monitoring
- **Web Dashboard**: Visual interface for status monitoring
- **Test Coverage**: Further improvement to 90%+ coverage

---
