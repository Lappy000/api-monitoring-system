"""FastAPI application entry point for API Monitor."""

import asyncio
import signal
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_config, Config
from app.database.base import Base
from app.database.session import engine, async_session
from app.models.endpoint import Endpoint
from app.core.health_checker import HealthChecker
from app.core.notifications import NotificationManager
from app.core.scheduler import MonitoringScheduler, set_scheduler
from app.utils.logger import setup_logging, get_logger
from app.api import endpoints, stats, health
from app import __version__
from sqlalchemy import select

# Initialize logger
logger = get_logger(__name__)

# Global instances
health_checker: HealthChecker
notification_manager: NotificationManager
scheduler: MonitoringScheduler


async def load_config_endpoints(config: Config) -> None:
    """
    Load endpoints from configuration into database.
    
    This function ensures that endpoints defined in config.yaml are
    created in the database on application startup.
    
    Args:
        config: Application configuration
    """
    if not config.endpoints:
        logger.info("No endpoints defined in configuration")
        return
    
    async with async_session() as db:
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
    
    config = get_config()
    
    # Setup logging
    setup_logging(
        level=config.logging.level,
        log_format=config.logging.format,
        log_file=config.logging.file,
        console=config.logging.console
    )
    
    # Create data directory if it doesn't exist
    from pathlib import Path
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    logger.info(f"Ensured data directory exists: {data_dir.absolute()}")
    
    # Create database tables
    logger.info("Creating database tables")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Load endpoints from config into database
    await load_config_endpoints(config)
    
    # Initialize global instances
    global health_checker, notification_manager, scheduler
    
    health_checker = HealthChecker(
        max_concurrent=config.monitoring.max_concurrent_checks,
        default_timeout=5
    )
    
    notification_manager = NotificationManager(config.notifications)
    
    scheduler = MonitoringScheduler(
        config=config,
        health_checker=health_checker,
        notification_manager=notification_manager
    )
    
    # Set global scheduler instance
    set_scheduler(scheduler)
    
    # Start scheduler
    await scheduler.start()
    
    logger.info(
        "API Monitor started successfully",
        extra={
            "version": __version__,
            "database": config.database.type,
            "api_port": config.api.port
        }
    )
    
    yield
    
    # Shutdown
    logger.info("Shutting down API Monitor application")
    
    # Stop scheduler
    await scheduler.stop()
    
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


# Configure CORS
config = get_config()
if config.api.cors.enabled:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.api.cors.allow_origins,
        allow_credentials=config.api.cors.allow_credentials,
        allow_methods=config.api.cors.allow_methods,
        allow_headers=config.api.cors.allow_headers,
    )
    logger.info("CORS middleware enabled")


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.exception(
        "Unhandled exception",
        extra={
            "path": request.url.path,
            "method": request.method,
            "error": str(exc)
        }
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error": str(exc) if config.api.host == "0.0.0.0" else "An error occurred"
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
        "health": "/health"
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
    
    config = get_config()
    
    uvicorn.run(
        "app.main:app",
        host=config.api.host,
        port=config.api.port,
        reload=config.api.reload,
        workers=config.api.workers if not config.api.reload else 1,
        log_level=config.logging.level.lower()
    )