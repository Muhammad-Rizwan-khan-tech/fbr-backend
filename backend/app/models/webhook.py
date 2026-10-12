from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.base import generate_uuid, TenantMixin, TimestampMixin


class WebhookEndpoint(Base, TenantMixin):
    __tablename__ = "webhook_endpoints"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    url = Column(String(500), nullable=False)
    secret = Column(String(64), nullable=False)  # whsec_...
    description = Column(String(255), nullable=True)
    events = Column(String(500), default="*", nullable=False)  # comma-separated or *
    is_active = Column(Boolean, default=True, nullable=False)
    failure_count = Column(Integer, default=0, nullable=False)
    last_delivery_at = Column(DateTime(timezone=True), nullable=True)

    deliveries = relationship("WebhookDelivery", back_populates="endpoint", cascade="all, delete-orphan")


class WebhookDelivery(Base, TimestampMixin):
    __tablename__ = "webhook_deliveries"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    endpoint_id = Column(String(36), ForeignKey("webhook_endpoints.id"), nullable=False, index=True)
    tenant_id = Column(String(36), nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    payload = Column(Text, nullable=False)
    response_status = Column(Integer, nullable=True)
    response_body = Column(String(1000), nullable=True)
    duration_ms = Column(Integer, default=0, nullable=False)
    attempt = Column(Integer, default=1, nullable=False)
    status = Column(String(20), default="PENDING", nullable=False, index=True)  # SUCCESS | FAILED | RETRYING
    error_message = Column(String(500), nullable=True)

    endpoint = relationship("WebhookEndpoint", back_populates="deliveries")
