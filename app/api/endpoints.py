"""Endpoint management API routes."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database.session import get_db
from app.models.endpoint import Endpoint
from app.schemas.endpoint import (
    EndpointCreate,
    EndpointUpdate,
    EndpointResponse,
    EndpointListResponse,
    CheckManualRequest,
    CheckManualResponse
)
from app.core.health_checker import HealthChecker
from app.core.scheduler import get_scheduler
from app.utils.logger import get_logger
from app.core.metrics import metrics_collector
from app.core.rate_limiter import limiter

router = APIRouter()
logger = get_logger(__name__)


@router.get("/endpoints", response_model=EndpointListResponse)
@limiter.limit("100/minute")
async def list_endpoints(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    List all endpoints.
    
    Args:
        request: FastAPI request object
        skip: Number of records to skip
        limit: Maximum number of records to return
        active_only: Filter only active endpoints
        db: Database session
    """
    
    query = select(Endpoint)
    
    if active_only:
        query = query.where(Endpoint.is_active == True)
    
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    endpoints = result.scalars().all()
    
    # Get total count
    count_result = await db.execute(select(Endpoint))
    total = len(count_result.scalars().all())
    
    logger.info(f"Listed {len(endpoints)} endpoints")
    
    return EndpointListResponse(
        endpoints=[EndpointResponse.model_validate(e) for e in endpoints],
        total=total
    )


@router.post("/endpoints", response_model=EndpointResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("50/minute")
async def create_endpoint(
    request: Request,
    endpoint_data: EndpointCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new endpoint.
    
    Args:
        endpoint_data: Endpoint creation data
        db: Database session
    """
    # Check if endpoint with same name already exists
    result = await db.execute(
        select(Endpoint).where(Endpoint.name == endpoint_data.name)
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Endpoint with name '{endpoint_data.name}' already exists"
        )
    
    # Create new endpoint
    endpoint = Endpoint(**endpoint_data.model_dump())
    db.add(endpoint)
    await db.commit()
    await db.refresh(endpoint)
    
    # Add to scheduler if active
    scheduler = get_scheduler()
    if scheduler and endpoint.is_active:
        await scheduler.add_endpoint_job(endpoint)
    
    logger.info(
        f"Created endpoint",
        extra={
            "endpoint_id": endpoint.id,
            "endpoint_name": endpoint.name
        }
    )
    
    return EndpointResponse.model_validate(endpoint)


@router.get("/endpoints/{endpoint_id}", response_model=EndpointResponse)
@limiter.limit("200/minute")
async def get_endpoint(
    request: Request,
    endpoint_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get endpoint by ID.
    
    Args:
        endpoint_id: Endpoint ID
        db: Database session
    """
    result = await db.execute(
        select(Endpoint).where(Endpoint.id == endpoint_id)
    )
    endpoint = result.scalar_one_or_none()
    
    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Endpoint {endpoint_id} not found"
        )
    
    return EndpointResponse.model_validate(endpoint)


@router.put("/endpoints/{endpoint_id}", response_model=EndpointResponse)
@limiter.limit("50/minute")
async def update_endpoint(
    request: Request,
    endpoint_id: int,
    endpoint_data: EndpointUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update an endpoint.
    
    Args:
        endpoint_id: Endpoint ID
        endpoint_data: Update data
        db: Database session
    """
    result = await db.execute(
        select(Endpoint).where(Endpoint.id == endpoint_id)
    )
    endpoint = result.scalar_one_or_none()
    
    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Endpoint {endpoint_id} not found"
        )
    
    # Update fields
    update_data = endpoint_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(endpoint, field, value)
    
    await db.commit()
    await db.refresh(endpoint)
    
    # Update scheduler job
    scheduler = get_scheduler()
    if scheduler:
        await scheduler.update_endpoint_job(endpoint)
    
    logger.info(
        f"Updated endpoint",
        extra={
            "endpoint_id": endpoint.id,
            "endpoint_name": endpoint.name
        }
    )
    
    return EndpointResponse.model_validate(endpoint)


@router.delete("/endpoints/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute")
async def delete_endpoint(
    request: Request,
    endpoint_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete an endpoint.
    
    Args:
        endpoint_id: Endpoint ID
        db: Database session
    """
    result = await db.execute(
        select(Endpoint).where(Endpoint.id == endpoint_id)
    )
    endpoint = result.scalar_one_or_none()
    
    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Endpoint {endpoint_id} not found"
        )
    
    # Remove from scheduler
    scheduler = get_scheduler()
    if scheduler:
        await scheduler.remove_endpoint_job(endpoint_id)
    
    # Delete from database
    await db.delete(endpoint)
    await db.commit()
    
    logger.info(
        f"Deleted endpoint",
        extra={
            "endpoint_id": endpoint_id,
            "endpoint_name": endpoint.name
        }
    )


@router.post("/endpoints/{endpoint_id}/check", response_model=CheckManualResponse)
@limiter.limit("30/minute")
async def manual_check(
    request: Request,
    endpoint_id: int,
    check_request: CheckManualRequest = CheckManualRequest(),
    db: AsyncSession = Depends(get_db)
):
    """
    Trigger a manual health check for an endpoint.
    
    Args:
        endpoint_id: Endpoint ID
        request: Check request parameters
        db: Database session
    """
    result = await db.execute(
        select(Endpoint).where(Endpoint.id == endpoint_id)
    )
    endpoint = result.scalar_one_or_none()
    
    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Endpoint {endpoint_id} not found"
        )
    
    # Perform health check
    health_checker = HealthChecker()
    await health_checker.start()
    
    try:
        check_result = await health_checker.check_and_save(endpoint, db)
        
        logger.info(
            f"Manual check completed",
            extra={
                "endpoint_id": endpoint.id,
                "success": check_result.success
            }
        )
        
        return CheckManualResponse(
            success=check_result.success,
            status_code=check_result.status_code,
            response_time=check_result.response_time,
            error_message=check_result.error_message,
            checked_at=check_result.checked_at
        )
    finally:
        await health_checker.close()