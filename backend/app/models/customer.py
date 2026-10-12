from sqlalchemy import Column, String, Boolean, ForeignKey, Text
from backend.app.core.database import Base
from backend.app.models.base import generate_uuid, TenantMixin


class Customer(Base, TenantMixin):
    __tablename__ = "customers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False, index=True)
    ntn = Column(String(20), nullable=True, index=True)
    strn = Column(String(30), nullable=True, index=True)
    cnic = Column(String(20), nullable=True, index=True)
    registration_type = Column(String(50), default="REGISTERED", nullable=False) # REGISTERED, UNREGISTERED
    buyer_type = Column(String(50), default="B2B", nullable=False) # B2B, B2C, EXPORT, GOVT
    
    address = Column(Text, nullable=False)
    city = Column(String(100), nullable=False)
    province = Column(String(100), nullable=False)
    postal_code = Column(String(20), nullable=True)
    country = Column(String(100), default="Pakistan", nullable=False)
    
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    buyer_reference = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
