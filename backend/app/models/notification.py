from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text

from backend.app.core.database import Base
from backend.app.models.base import generate_uuid, now_utc


class Notification(Base):
    """In-app notification. One row per recipient user."""
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    severity = Column(String(10), nullable=False, default="INFO")  # INFO | SUCCESS | WARNING | ERROR
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    entity_type = Column(String(30), nullable=True)
    entity_id = Column(String(36), nullable=True)
    is_read = Column(Boolean, nullable=False, default=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    correlation_id = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_utc)

    __table_args__ = (Index("ix_notifications_user_unread", "tenant_id", "user_id", "is_read"),)


class NotificationDelivery(Base):
    """Delivery record for out-of-app channels (email now; SMS/WhatsApp/webhook later)."""
    __tablename__ = "notification_deliveries"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    channel = Column(String(20), nullable=False)               # EMAIL | (future) SMS | WHATSAPP | WEBHOOK
    recipient = Column(String(255), nullable=False)
    subject = Column(String(300), nullable=True)
    status = Column(String(15), nullable=False, default="PENDING")  # PENDING | SENT | FAILED | SKIPPED
    attempt_count = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    correlation_id = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_utc)
    sent_at = Column(DateTime(timezone=True), nullable=True)
