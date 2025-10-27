"""CheckResult model - stores results of endpoint health checks."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database.base import Base


class CheckResult(Base):
    """
    CheckResult model representing the result of an endpoint health check.
    
    Attributes:
        id: Primary key
        endpoint_id: Foreign key to endpoint
        status_code: HTTP status code received (null if request failed)
        response_time: Response time in seconds
        success: Whether the check was successful
        error_message: Error details if check failed
        checked_at: Timestamp when check was performed
        endpoint: Relationship to endpoint
    """
    
    __tablename__ = "check_results"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign key to endpoint
    endpoint_id = Column(
        Integer,
        ForeignKey("endpoints.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Check results
    status_code = Column(Integer, nullable=True)
    response_time = Column(Float, nullable=True)  # in seconds
    success = Column(Boolean, nullable=False, default=False)
    error_message = Column(Text, nullable=True)
    
    # Timestamp
    checked_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    endpoint = relationship("Endpoint", back_populates="check_results")
    
    def __repr__(self) -> str:
        """String representation of check result."""
        return (
            f"<CheckResult(id={self.id}, endpoint_id={self.endpoint_id}, "
            f"success={self.success}, status_code={self.status_code})>"
        )
    
    def to_dict(self) -> dict:
        """Convert check result to dictionary."""
        return {
            "id": self.id,
            "endpoint_id": self.endpoint_id,
            "status_code": self.status_code,
            "response_time": self.response_time,
            "success": self.success,
            "error_message": self.error_message,
            "checked_at": self.checked_at.isoformat() if self.checked_at else None,
        }