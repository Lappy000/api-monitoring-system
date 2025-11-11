"""Health check endpoints."""

from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app import __version__
from app.schemas.stats import HealthResponse
from app.core.scheduler import get_scheduler
from app.core.circuit_breaker import circuit_breaker_registry

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


@router.get("/health/circuit-breakers")
async def circuit_breaker_status() -> JSONResponse:
    """
    Get status of all circuit breakers.
    
    Returns detailed state information for monitoring and debugging.
    """
    states = circuit_breaker_registry.get_all_states()
    
    # Summary statistics
    total = len(states)
    open_count = sum(1 for s in states.values() if s['state'] == 'open')
    half_open_count = sum(1 for s in states.values() if s['state'] == 'half_open')
    closed_count = sum(1 for s in states.values() if s['state'] == 'closed')
    
    return JSONResponse({
        "timestamp": datetime.utcnow().isoformat(),
        "summary": {
            "total_circuit_breakers": total,
            "open": open_count,
            "half_open": half_open_count,
            "closed": closed_count
        },
        "circuit_breakers": states
    })