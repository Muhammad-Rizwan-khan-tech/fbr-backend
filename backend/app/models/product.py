from sqlalchemy import Column, String, Boolean, Numeric, Text
from backend.app.core.database import Base
from backend.app.models.base import generate_uuid, TenantMixin


class Product(Base, TenantMixin):
    __tablename__ = "products"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    item_code = Column(String(100), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # FBR Tax Classification
    hs_code = Column(String(20), nullable=False) # e.g. "8471.30.10"
    uom = Column(String(20), default="NOS", nullable=False) # e.g. "NOS", "KGS"
    sale_type = Column(String(50), default="STANDARD", nullable=False)
    tax_rate = Column(Numeric(5, 2), default=18.00, nullable=False) # e.g. 18.00
    sro_reference = Column(String(100), nullable=True)
    
    unit_price = Column(Numeric(12, 2), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
