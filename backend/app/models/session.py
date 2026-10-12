from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.base import generate_uuid, TimestampMixin


class DeviceSession(Base, TimestampMixin):
    __tablename__ = "device_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    device_id = Column(String(36), ForeignKey("device_installations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    refresh_token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)

    # Relationships
    device = relationship("DeviceInstallation", back_populates="sessions")
    user = relationship("User")
    organization = relationship("Organization")
