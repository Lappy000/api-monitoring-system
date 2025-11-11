"""Statistics and analytics API routes."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database.session import get_db
from app.models.endpoint import Endpoint
from app.models.check_result import CheckResult
from app.core.uptime import UptimeCalculator
from app.schemas.stats import (
    UptimeStatsResponse,
    CheckHistoryResponse,
    CheckResultResponse,
    DowntimeIncidentsResponse,
    DowntimeIncident,
    OverallSummaryResponse
)
from app.utils.logger import get_logger
from app.core.rate_limiter import limiter

router = APIRouter()
logger = get_logger(__name__)


@router.get("/stats/uptime/{endpoint_id}", response_model=UptimeStatsResponse)
@limiter.limit("200/minute")
async def get_uptime_stats(
    request: Request,
    endpoint_id: int,
    period: str = Query(default="24h", pattern="^(24h|7d|30d)$"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get uptime statistics for an endpoint.
    
    Args:
        endpoint_id: Endpoint ID
        period: Time period (24h, 7d, 30d)
        db: Database session
    """
    # Verify endpoint exists
    result = await db.execute(
        select(Endpoint).where(Endpoint.id == endpoint_id)
    )
    endpoint = result.scalar_one_or_none()
    
    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Endpoint {endpoint_id} not found"
        )
    
    # Calculate statistics
    calculator = UptimeCalculator(db)
    stats = await calculator.get_statistics(endpoint_id, period)
    
    logger.info(
        f"Retrieved uptime stats",
        extra={
            "endpoint_id": endpoint_id,
            "period": period,
            "uptime": stats["uptime_percentage"]
        }
    )
    
    return UptimeStatsResponse(**stats)


@router.get("/stats/history/{endpoint_id}", response_model=CheckHistoryResponse)
@limiter.limit("200/minute")
async def get_check_history(
    request: Request,
    endpoint_id: int,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Get check history for an endpoint.
    
    Args:
        endpoint_id: Endpoint ID
        limit: Maximum number of results
        offset: Number of results to skip
        from_date: Start date (ISO format)
        to_date: End date (ISO format)
        db: Database session
    """
    # Verify endpoint exists
    result = await db.execute(
        select(Endpoint).where(Endpoint.id == endpoint_id)
    )
    endpoint = result.scalar_one_or_none()
    
    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Endpoint {endpoint_id} not found"
        )
    
    # Build query
    query = select(CheckResult).where(CheckResult.endpoint_id == endpoint_id)
    
    # Apply date filters
    if from_date:
        try:
            from_dt = datetime.fromisoformat(from_date)
            query = query.where(CheckResult.checked_at >= from_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid from_date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"
            )
    
    if to_date:
        try:
            to_dt = datetime.fromisoformat(to_date)
            query = query.where(CheckResult.checked_at <= to_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid to_date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"
            )
    
    # Get total count
    count_result = await db.execute(query)
    total = len(count_result.scalars().all())
    
    # Apply pagination and ordering
    query = query.order_by(CheckResult.checked_at.desc()).offset(offset).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    checks = result.scalars().all()
    
    logger.info(
        f"Retrieved check history",
        extra={
            "endpoint_id": endpoint_id,
            "count": len(checks),
            "total": total
        }
    )
    
    return CheckHistoryResponse(
        endpoint_id=endpoint_id,
        endpoint_name=endpoint.name,
        checks=[CheckResultResponse.model_validate(c) for c in checks],
        total=total,
        from_date=from_date,
        to_date=to_date
    )


@router.get("/stats/incidents/{endpoint_id}", response_model=DowntimeIncidentsResponse)
@limiter.limit("100/minute")
async def get_downtime_incidents(
    request: Request,
    endpoint_id: int,
    period: str = Query(default="7d", pattern="^(24h|7d|30d)$"),
    min_duration: int = Query(default=1, ge=1, description="Minimum duration in minutes"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get downtime incidents for an endpoint.
    
    Args:
        endpoint_id: Endpoint ID
        period: Time period (24h, 7d, 30d)
        min_duration: Minimum incident duration in minutes
        db: Database session
    """
    # Verify endpoint exists
    result = await db.execute(
        select(Endpoint).where(Endpoint.id == endpoint_id)
    )
    endpoint = result.scalar_one_or_none()
    
    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Endpoint {endpoint_id} not found"
        )
    
    # Get incidents
    calculator = UptimeCalculator(db)
    incidents = await calculator.get_downtime_incidents(
        endpoint_id,
        period,
        min_duration_minutes=min_duration
    )
    
    logger.info(
        f"Retrieved downtime incidents",
        extra={
            "endpoint_id": endpoint_id,
            "period": period,
            "incident_count": len(incidents)
        }
    )
    
    return DowntimeIncidentsResponse(
        endpoint_id=endpoint_id,
        endpoint_name=endpoint.name,
        period=period,
        incidents=[DowntimeIncident(**inc) for inc in incidents],
        total_incidents=len(incidents)
    )


@router.get("/stats/summary", response_model=OverallSummaryResponse)
@limiter.limit("100/minute")
async def get_overall_summary(request: Request, db:AsyncSession = Depends(get_db)):
    """
    Get overall summary statistics for all endpoints.
    
    Args:
        db: Database session
    """
    calculator = UptimeCalculator(db)
    summary = await calculator.get_overall_summary()
    
    logger.info(
        f"Retrieved overall summary",
        extra={
            "total_endpoints": summary["total_endpoints"],
            "healthy": summary["healthy_endpoints"]
        }
    )
    
    return OverallSummaryResponse(**summary)