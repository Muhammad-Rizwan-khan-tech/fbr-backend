import enum
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.base import generate_uuid, now_utc, TimestampMixin


class DeviceStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


class DeviceInstallation(Base, TimestampMixin):
    __tablename__ = "device_installations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    license_id = Column(String(36), ForeignKey("licenses.id", ondelete="CASCADE"), nullable=False, index=True)
    device_fingerprint = Column(String(64), nullable=False, index=True)
    device_name = Column(String(100), default="Windows Terminal", nullable=False)
    os_info = Column(String(100), default="Windows", nullable=False)
    app_version = Column(String(50), default="1.0.0", nullable=False)
    ip_address = Column(String(50), nullable=True)
    status = Column(String(50), default=DeviceStatus.ACTIVE.value, nullable=False)
    activated_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    last_seen_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by = Column(String(100), nullable=True)
    revocation_reason = Column(Text, nullable=True)

    # Relationships
    license = relationship("License", back_populates="devices")
    organization = relationship("Organization")
    sessions = relationship("DeviceSession", back_populates="device", cascade="all, delete-orphan")
