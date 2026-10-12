import enum
from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.base import generate_uuid, TimestampMixin


class PlanTier(str, enum.Enum):
    STARTER = "STARTER"
    PROFESSIONAL = "PROFESSIONAL"
    BUSINESS = "BUSINESS"
    ENTERPRISE = "ENTERPRISE"


class OrgStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    TRIAL = "TRIAL"


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    plan = Column(String(50), default=PlanTier.STARTER.value, nullable=False)
    status = Column(String(50), default=OrgStatus.ACTIVE.value, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    settings = relationship("OrganizationSettings", back_populates="organization", uselist=False, cascade="all, delete-orphan")
    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    taxpayer = relationship("Taxpayer", back_populates="organization", uselist=False, cascade="all, delete-orphan")
    branches = relationship("Branch", back_populates="organization", cascade="all, delete-orphan")


class OrganizationSettings(Base, TimestampMixin):
    __tablename__ = "organization_settings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, nullable=False)
    invoice_prefix = Column(String(20), default="INV", nullable=False)
    next_invoice_number = Column(Integer, default=1001, nullable=False)
    credit_note_prefix = Column(String(20), default="CRN", nullable=False)
    debit_note_prefix = Column(String(20), default="DBN", nullable=False)
    default_terms = Column(Text, nullable=True)
    fbr_mode = Column(String(50), default="DEMO", nullable=False)  # DEMO, SANDBOX, PRODUCTION
    enable_auto_submit = Column(Boolean, default=False, nullable=False)
    fbr_pos_id = Column(String(50), nullable=True)
    fbr_api_token = Column(String(500), nullable=True)
    fbr_base_url = Column(String(255), nullable=True)

    organization = relationship("Organization", back_populates="settings")


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    plan = Column(String(50), default=PlanTier.STARTER.value, nullable=False)
    status = Column(String(50), default="ACTIVE", nullable=False)
    monthly_invoice_limit = Column(Integer, default=100, nullable=False)
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)


class SubscriptionUsage(Base, TimestampMixin):
    __tablename__ = "subscription_usage"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    period = Column(String(7), nullable=False)  # YYYY-MM
    invoices_created = Column(Integer, default=0, nullable=False)
    fbr_submissions_count = Column(Integer, default=0, nullable=False)
