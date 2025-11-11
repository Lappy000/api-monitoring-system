"""Audit log model for tracking system events and user actions."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON

from app.database.base import Base


class AuditLog(Base):
    """Audit log model for tracking system events and user actions."""
    
    __tablename__ = "audit_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str] = mapped_column(String(100), nullable=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    details: Mapped[dict] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    
    def __repr__(self) -> str:
        """String representation of audit log entry."""
        return (
            f"<AuditLog("
            f"id={self.id}, "
            f"action='{self.action}', "
            f"timestamp='{self.timestamp.isoformat()}', "
            f"status='{self.status}'"
            f")>"
        )