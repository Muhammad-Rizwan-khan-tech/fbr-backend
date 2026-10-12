import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey
from backend.app.core.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)


class TenantMixin(TimestampMixin):
    tenant_id = Column(String(36), nullable=False, index=True)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)
