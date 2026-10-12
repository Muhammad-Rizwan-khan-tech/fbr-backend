import enum
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.base import generate_uuid, now_utc, TimestampMixin


class LicenseStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    SUSPENDED = "SUSPENDED"


class ActivationKeyStatus(str, enum.Enum):
    PENDING = "PENDING"
    REDEEMED = "REDEEMED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class License(Base, TimestampMixin):
    __tablename__ = "licenses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    license_number = Column(String(100), unique=True, nullable=False, index=True)
    license_type = Column(String(50), default="PERMANENT", nullable=False)
    status = Column(String(50), default=LicenseStatus.ACTIVE.value, nullable=False)
    max_devices = Column(Integer, default=5, nullable=False)
    issued_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    issued_by = Column(String(100), default="SUPER_ADMIN", nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by = Column(String(100), nullable=True)
    revocation_reason = Column(Text, nullable=True)

    # Relationships
    organization = relationship("Organization", backref="licenses")
    activation_keys = relationship("ActivationKey", back_populates="license", cascade="all, delete-orphan")
    devices = relationship("DeviceInstallation", back_populates="license", cascade="all, delete-orphan")


class ActivationKey(Base, TimestampMixin):
    __tablename__ = "activation_keys"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    license_id = Column(String(36), ForeignKey("licenses.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    key_hash = Column(String(64), unique=True, nullable=False, index=True)
    key_prefix = Column(String(20), nullable=False)
    status = Column(String(50), default=ActivationKeyStatus.PENDING.value, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    redeemed_at = Column(DateTime(timezone=True), nullable=True)
    redeemed_device_id = Column(String(36), nullable=True)
    created_by = Column(String(100), default="SUPER_ADMIN", nullable=False)

    # Relationships
    license = relationship("License", back_populates="activation_keys")
    organization = relationship("Organization")
