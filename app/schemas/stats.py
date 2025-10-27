"""Pydantic schemas for statistics endpoints."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class UptimeStatsResponse(BaseModel):
    """Schema for uptime statistics response."""
    endpoint_id: int
    endpoint_name: str
    period: str
    uptime_percentage: float
    total_checks: int
    successful_checks: int
    failed_checks: int
    avg_response_time: Optional[float] = None
    min_response_time: Optional[float] = None
    max_response_time: Optional[float] = None
    last_check: Optional[str] = None
    last_success: Optional[str] = None
    last_failure: Optional[str] = None


class CheckResultResponse(BaseModel):
    """Schema for a single check result."""
    id: int
    endpoint_id: int
    status_code: Optional[int] = None
    response_time: Optional[float] = None
    success: bool
    error_message: Optional[str] = None
    checked_at: datetime
    
    model_config = {"from_attributes": True}


class CheckHistoryResponse(BaseModel):
    """Schema for check history response."""
    endpoint_id: int
    endpoint_name: str
    checks: List[CheckResultResponse]
    total: int
    from_date: Optional[str] = None
    to_date: Optional[str] = None


class DowntimeIncident(BaseModel):
    """Schema for a single downtime incident."""
    start: str
    end: str
    duration_minutes: float
    failure_count: int
    errors: List[str]


class DowntimeIncidentsResponse(BaseModel):
    """Schema for downtime incidents response."""
    endpoint_id: int
    endpoint_name: str
    period: str
    incidents: List[DowntimeIncident]
    total_incidents: int


class OverallSummaryResponse(BaseModel):
    """Schema for overall summary response."""
    total_endpoints: int
    active_endpoints: int
    inactive_endpoints: int
    healthy_endpoints: int
    unhealthy_endpoints: int
    timestamp: str


class HealthResponse(BaseModel):
    """Schema for health check response."""
    status: str = Field(default="healthy")
    version: str
    timestamp: str
    database: str = Field(default="connected")
    scheduler: str = Field(default="running")