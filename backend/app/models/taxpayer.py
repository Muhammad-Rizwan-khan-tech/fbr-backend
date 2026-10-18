from sqlalchemy import Column, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.base import generate_uuid, TimestampMixin


class Taxpayer(Base, TimestampMixin):
    __tablename__ = "taxpayers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    
    # Pakistan Tax Identification
    legal_name = Column(String(255), nullable=False)
    trade_name = Column(String(255), nullable=True)
    ntn = Column(String(20), nullable=False, index=True)  # Format: 1234567-8 or 7-8 digits
    strn = Column(String(30), nullable=True, index=True) # Sales Tax Registration Number
    registration_type = Column(String(50), default="REGISTERED", nullable=False)
    business_type = Column(String(100), default="WHOLESALER", nullable=False)
    business_activity = Column(String(100), default="WHOLESALER", nullable=False)  # MANUFACTURER, DISTRIBUTOR, WHOLESALER, EXPORTER, RETAILER, SERVICE_PROVIDER, OTHER
    business_sector = Column(String(100), default="General Trading", nullable=True)
    
    # Address details
    address = Column(Text, nullable=False)
    city = Column(String(100), nullable=False)
    province = Column(String(100), nullable=False) # Sindh, Punjab, etc.
    postal_code = Column(String(20), nullable=True)
    country = Column(String(100), default="Pakistan", nullable=False)
    
    # Contact info
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    website = Column(String(255), nullable=True)
    
    # Branding & signature
    logo_url = Column(String(500), nullable=True)
    authorized_signatory_name = Column(String(255), nullable=True)
    authorized_signatory_designation = Column(String(255), nullable=True)

    organization = relationship("Organization", back_populates="taxpayer")
