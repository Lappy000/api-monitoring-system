"""Pydantic schemas for endpoint operations."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, HttpUrl


class EndpointBase(BaseModel):
    """Base schema for endpoint data."""
    name: str = Field(..., min_length=1, max_length=255, description="Endpoint name")
    url: str = Field(..., description="Full URL to monitor")
    method: str = Field(default="GET", description="HTTP method")
    interval: int = Field(default=60, ge=10, description="Check interval in seconds")
    timeout: int = Field(default=5, ge=1, description="Request timeout in seconds")
    expected_status: int = Field(default=200, ge=100, le=599, description="Expected HTTP status code")
    headers: Optional[Dict[str, str]] = Field(default=None, description="Custom HTTP headers")
    body: Optional[Dict[str, Any]] = Field(default=None, description="Request body for POST/PUT")
    is_active: bool = Field(default=True, description="Whether monitoring is enabled")


class EndpointCreate(EndpointBase):
    """Schema for creating a new endpoint."""
    pass


class EndpointUpdate(BaseModel):
    """Schema for updating an endpoint (all fields optional)."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    url: Optional[str] = None
    method: Optional[str] = None
    interval: Optional[int] = Field(None, ge=10)
    timeout: Optional[int] = Field(None, ge=1)
    expected_status: Optional[int] = Field(None, ge=100, le=599)
    headers: Optional[Dict[str, str]] = None
    body: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class EndpointResponse(EndpointBase):
    """Schema for endpoint response."""
    id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class EndpointListResponse(BaseModel):
    """Schema for list of endpoints."""
    endpoints: List[EndpointResponse]
    total: int
    
    model_config = {"from_attributes": True}


class CheckManualRequest(BaseModel):
    """Schema for manual check request."""
    use_retry: bool = Field(default=True, description="Whether to use retry mechanism")


class CheckManualResponse(BaseModel):
    """Schema for manual check response."""
    success: bool
    status_code: Optional[int] = None
    response_time: Optional[float] = None
    error_message: Optional[str] = None
    checked_at: datetime
    
    model_config = {"from_attributes": True}