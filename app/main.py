"""FastAPI application entry point for API Monitor."""

import asyncio
import signal
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, Request, Depends
from sqlalchemy import select
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import load_config, Config
from app.core.rate_limiter import limiter
from app.database.base import Base
from app.database.session import engine, async_session
from app.models.endpoint import Endpoint
from app.core.health_checker import HealthChecker
from app.core.notifications import NotificationManager
from app.core.scheduler import MonitoringScheduler, set_scheduler
from app.utils.logger import setup_logging, get_logger
from app.api import endpoints, stats, health
from app.core.auth import api_key_auth, require_auth, verify_api_key
from app import __version__

# Initialize logger
logger = get_logger(__name__)

# Global instances with type hints
health_checker: Optional[HealthChecker] = None
notification_manager: Optional[NotificationManager] = None
scheduler: Optional[MonitoringScheduler] = None
app_config: Optional[Config] = None

# Load configuration at module level to avoid race condition
# This ensures config is available before middleware runs
try:
    app_config = load_config()
    logger.info("Configuration loaded at module level")
except Exception as e:
    logger.error(f"Failed to load configuration: {e}")
    # Continue without config - will be loaded in lifespan as fallback


async def load_config_endpoints(config: Config, db) -> None:
    """
    Load endpoints from configuration into database.
    
    This function ensures that endpoints defined in config.yaml are
    created in the database on application startup.
    
    Args:
        config: Application configuration
        db: Database session
    """
    if not config.endpoints:
        logger.info("No endpoints defined in configuration")
        return
    
    loaded_count = 0
    updated_count = 0
    
    for endpoint_config in config.endpoints:
        # Check if endpoint already exists
        result = await db.execute(
            select(Endpoint).where(Endpoint.name == endpoint_config.name)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing endpoint
            existing.url = endpoint_config.url
            existing.method = endpoint_config.method
            existing.interval = endpoint_config.interval
            existing.timeout = endpoint_config.timeout
            existing.expected_status = endpoint_config.expected_status
            existing.headers = endpoint_config.headers or {}
            existing.body = endpoint_config.body
            existing.is_active = endpoint_config.is_active
            updated_count += 1
            
            logger.info(
                f"Updated endpoint from config",
                extra={
                    "endpoint_id": existing.id,
                    "endpoint_name": existing.name
                }
            )
        else:
            # Create new endpoint
            endpoint = Endpoint(
                name=endpoint_config.name,
                url=endpoint_config.url,
                method=endpoint_config.method,
                interval=endpoint_config.interval,
                timeout=endpoint_config.timeout,
                expected_status=endpoint_config.expected_status,
                headers=endpoint_config.headers or {},
                body=endpoint_config.body,
                is_active=endpoint_config.is_active
            )
            db.add(endpoint)
            loaded_count += 1
            
            logger.info(
                f"Created endpoint from config",
                extra={"endpoint_name": endpoint_config.name}
            )
    
    await db.commit()
    
    logger.info(
        f"Loaded endpoints from configuration",
        extra={
            "endpoints_created": loaded_count,
            "endpoints_updated": updated_count,
            "total_endpoints": len(config.endpoints)
        }
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Lifespan context manager for FastAPI application.
    
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting API Monitor application")
    
    # Use the already-loaded config from module level
    # Don't load it again - this is wasteful
    if app_config is None:
        raise RuntimeError("Configuration not loaded at module level")
    
    # Store config and components on app.state for proper dependency injection
    app.state.config = app_config
    # Limiter is already initialized at app creation
    
    # Setup logging
    setup_logging(
        level=app_config.logging.level,
        log_format=app_config.logging.format,
        log_file=app_config.logging.file,
        console=app_config.logging.console
    )
    
    # Create data directory if it doesn't exist
    from pathlib import Path
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    logger.info(f"Ensured data directory exists: {data_dir.absolute()}")
    
    # Create database tables - handle race conditions in multi-worker environments
    logger.info("Creating database tables")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, checkfirst=True)
    except Exception as e:
        # In multi-worker setup, another worker might have already created tables
        # This is expected and safe to ignore for "table already exists" errors
        if "already exists" in str(e).lower():
            logger.info("Database tables already exist (created by another worker)")
        else:
            # Re-raise if it's a different error
            raise
    
    # Load endpoints from config into database
    async with async_session() as db:
        await load_config_endpoints(app_config, db)
    
    # Initialize components
    health_checker = HealthChecker(
        max_concurrent=app_config.monitoring.max_concurrent_checks,
        default_timeout=5
    )
    app.state.health_checker = health_checker
    
    notification_manager = NotificationManager(app_config.notifications, app_config)
    app.state.notification_manager = notification_manager
    
    # Test Redis connectivity if enabled - fail fast if required
    if app_config.redis.enabled:
        redis_ok = await notification_manager.test_redis_connection()
        if not redis_ok:
            logger.warning(
                "Redis is enabled but connection failed. "
                "Cooldown will use in-memory storage (not shared across workers)"
            )
            # Optionally fail fast if Redis is critical:
            # raise RuntimeError("Redis enabled but connection failed")
    
    scheduler = MonitoringScheduler(
        config=app_config,
        health_checker=health_checker,
        notification_manager=notification_manager
    )
    app.state.scheduler = scheduler
    
    # Set global scheduler instance for backward compatibility
    set_scheduler(scheduler)
    
    # Start scheduler
    await scheduler.start()
    
    logger.info(
        "API Monitor started successfully",
        extra={
            "version": __version__,
            "database": app_config.database.type,
            "api_port": app_config.api.port,
            "auth_enabled": app_config.api.auth.enabled,
            "rate_limiting_enabled": True
        }
    )
    
    yield
    
    # Shutdown
    logger.info("Shutting down API Monitor application")
    
    # Stop scheduler
    if scheduler:
        await scheduler.stop()
    
    # Close notification manager
    if notification_manager:
        await notification_manager.close()
    
    # Close database connections
    await engine.dispose()
    
    logger.info("API Monitor shut down successfully")


# Create FastAPI application
app = FastAPI(
    title="API Monitor",
    description="Production-ready API monitoring system with health checks, uptime analytics, and notifications",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Store limiter on app.state for access in routes
app.state.limiter = limiter

# Configure CORS middleware at app creation (not in deprecated on_event)
if app_config and app_config.api.cors.enabled:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_config.api.cors.allow_origins,
        allow_credentials=app_config.api.cors.allow_credentials,
        allow_methods=app_config.api.cors.allow_methods,
        allow_headers=app_config.api.cors.allow_headers,
    )
    logger.info("CORS middleware enabled at app creation")


# Middleware for request ID and authentication
@app.middleware("http")
async def add_request_id_and_auth(request: Request, call_next):
    """
    Middleware to add request ID to all requests and handle authentication.
    """
    # Generate request ID
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    # Check authentication if enabled - config must be loaded from app.state
    if hasattr(request.app.state, 'config') and request.app.state.config.api.auth.enabled:
        try:
            # Skip auth for health, docs, and static endpoints
            # Use proper path matching to handle subpaths and avoid blocking Swagger UI
            skip_paths = ["/health", "/docs", "/redoc", "/openapi.json"]
            should_skip = False
            for path in skip_paths:
                if request.url.path == path or request.url.path.startswith(path + "/"):
                    should_skip = True
                    break
            
            if not should_skip:
                await verify_api_key(request, request.app.state.config)
        except Exception as e:
            return JSONResponse(
                status_code=401,
                content={"detail": str(e)},
                headers={"X-Request-ID": request_id}
            )
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.exception(
        "Unhandled exception",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "error": str(exc)
        }
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error": str(exc) if app_config and app_config.api.host == "0.0.0.0" else "An error occurred",
            "request_id": request_id
        },
        headers={"X-Request-ID": request_id}
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceeded errors."""
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.warning(
        "Rate limit exceeded",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "client": get_remote_address(request)
        }
    )
    
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded. Please try again later.",
            "request_id": request_id
        },
        headers={
            "X-Request-ID": request_id,
            "Retry-After": "60"
        }
    )


# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(endpoints.router, prefix="/api/v1", tags=["Endpoints"])
app.include_router(stats.router, prefix="/api/v1", tags=["Statistics"])


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "API Monitor",
        "version": __version__,
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "auth_enabled": app_config.api.auth.enabled if app_config else False
    }


# Graceful shutdown handler
def handle_shutdown_signal(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown")
    # FastAPI will handle the shutdown through lifespan


# Register signal handlers
signal.signal(signal.SIGTERM, handle_shutdown_signal)
signal.signal(signal.SIGINT, handle_shutdown_signal)


if __name__ == "__main__":
    import uvicorn
    
    # Load config for manual run
    if not app_config:
        app_config = load_config()
    
    uvicorn.run(
        "app.main:app",
        host=app_config.api.host,
        port=app_config.api.port,
        reload=app_config.api.reload,
        workers=app_config.api.workers if not app_config.api.reload else 1,
        log_level=app_config.logging.level.lower()
    )