"""Endpoint model - represents an API endpoint to monitor."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Boolean, JSON, DateTime
from sqlalchemy.orm import relationship

from app.database.base import Base


class Endpoint(Base):
    """
    Endpoint model representing an API endpoint to be monitored.
    
    Attributes:
        id: Primary key
        name: Human-readable endpoint name
        url: Full URL to monitor
        method: HTTP method (GET, POST, etc.)
        interval: Check interval in seconds
        timeout: Request timeout in seconds
        expected_status: Expected HTTP status code
        headers: Optional HTTP headers as JSON
        body: Optional request body as JSON (for POST requests)
        is_active: Whether monitoring is enabled
        created_at: Timestamp when endpoint was created
        updated_at: Timestamp of last update
        check_results: Relationship to check results
        notification_logs: Relationship to notification logs
    """
    
    __tablename__ = "endpoints"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Endpoint configuration
    name = Column(String(255), unique=True, nullable=False, index=True)
    url = Column(String(2048), nullable=False)
    method = Column(String(10), nullable=False, default="GET")
    interval = Column(Integer, nullable=False, default=60)
    timeout = Column(Integer, nullable=False, default=5)
    expected_status = Column(Integer, nullable=False, default=200)
    
    # Optional configuration
    headers = Column(JSON, nullable=True, default=dict)
    body = Column(JSON, nullable=True)
    
    # Status
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    # Relationships
    check_results = relationship(
        "CheckResult",
        back_populates="endpoint",
        cascade="all, delete-orphan"
    )
    notification_logs = relationship(
        "NotificationLog",
        back_populates="endpoint",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        """String representation of endpoint."""
        return f"<Endpoint(id={self.id}, name='{self.name}', url='{self.url}')>"
    
    def to_dict(self) -> dict:
        """Convert endpoint to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "method": self.method,
            "interval": self.interval,
            "timeout": self.timeout,
            "expected_status": self.expected_status,
            "headers": self.headers,
            "body": self.body,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }