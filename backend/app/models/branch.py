from sqlalchemy import Column, String, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.base import generate_uuid, TimestampMixin


class Branch(Base, TimestampMixin):
    __tablename__ = "branches"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    branch_name = Column(String(255), nullable=False)
    branch_code = Column(String(50), nullable=False) # e.g. KHI-01, LHR-MAIN
    fbr_pos_id = Column(String(50), nullable=True) # FBR POS / Branch ID
    address = Column(Text, nullable=False)
    city = Column(String(100), nullable=False)
    province = Column(String(100), nullable=False)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_main = Column(Boolean, default=False, nullable=False)

    organization = relationship("Organization", back_populates="branches")
