"""Health check endpoints."""

from datetime import datetime
from fastapi import APIRouter
from app import __version__
from app.schemas.stats import HealthResponse
from app.core.scheduler import get_scheduler

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Returns system health status including database connection and scheduler status.
    """
    scheduler = get_scheduler()
    
    return HealthResponse(
        status="healthy",
        version=__version__,
        timestamp=datetime.utcnow().isoformat(),
        database="connected",
        scheduler="running" if scheduler else "stopped"
    )