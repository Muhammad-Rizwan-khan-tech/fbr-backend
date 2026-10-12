from sqlalchemy import Column, String, DateTime, Text
from backend.app.core.database import Base
from backend.app.models.base import generate_uuid, now_utc


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    admin_identity = Column(String(100), default="SUPER_ADMIN", nullable=False, index=True)
    action = Column(String(100), nullable=False, index=True)
    target_type = Column(String(50), nullable=False, index=True)
    target_id = Column(String(36), nullable=False, index=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False, index=True)
