"""NotificationLog model - tracks sent notifications for audit and debugging."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database.base import Base


class NotificationLog(Base):
    """
    NotificationLog model representing a sent notification.
    
    Attributes:
        id: Primary key
        endpoint_id: Foreign key to endpoint
        notification_type: Type of notification (email, webhook, telegram)
        status: Status of notification (sent, failed, pending)
        message: Notification message content
        error_message: Error details if notification failed
        sent_at: Timestamp when notification was sent/attempted
        endpoint: Relationship to endpoint
    """
    
    __tablename__ = "notification_logs"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign key to endpoint
    endpoint_id = Column(
        Integer,
        ForeignKey("endpoints.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Notification details
    notification_type = Column(String(50), nullable=False)  # email, webhook, telegram
    status = Column(String(20), nullable=False, index=True)  # sent, failed, pending
    message = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Timestamp
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    endpoint = relationship("Endpoint", back_populates="notification_logs")
    
    def __repr__(self) -> str:
        """String representation of notification log."""
        return (
            f"<NotificationLog(id={self.id}, endpoint_id={self.endpoint_id}, "
            f"type={self.notification_type}, status={self.status})>"
        )
    
    def to_dict(self) -> dict:
        """Convert notification log to dictionary."""
        return {
            "id": self.id,
            "endpoint_id": self.endpoint_id,
            "notification_type": self.notification_type,
            "status": self.status,
            "message": self.message,
            "error_message": self.error_message,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
        }