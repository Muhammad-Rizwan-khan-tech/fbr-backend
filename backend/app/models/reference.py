from sqlalchemy import Column, String, Boolean, Numeric, Integer, Text
from backend.app.core.database import Base
from backend.app.models.base import generate_uuid, TimestampMixin


class HSCode(Base, TimestampMixin):
    __tablename__ = "hs_codes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    code = Column(String(20), unique=True, nullable=False, index=True) # e.g. "8471.30.10"
    description = Column(Text, nullable=False)
    chapter = Column(String(10), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)


class UOM(Base, TimestampMixin):
    __tablename__ = "uoms"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    code = Column(String(20), unique=True, nullable=False, index=True) # e.g. "NOS", "KGS", "LTR", "MTR"
    name = Column(String(100), nullable=False)
    fbr_code = Column(String(20), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)


class TaxRate(Base, TimestampMixin):
    __tablename__ = "tax_rates"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False) # e.g. "Standard Rate 18%", "Reduced Rate 1%", "Exempt 0%"
    rate_percent = Column(Numeric(5, 2), nullable=False)
    tax_type = Column(String(50), default="SALES_TAX", nullable=False) # SALES_TAX, FURTHER_TAX, WITHHOLDING
    province = Column(String(100), default="FEDERAL", nullable=False)
    sro_reference = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)


class SaleType(Base, TimestampMixin):
    __tablename__ = "sale_types"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    code = Column(String(50), unique=True, nullable=False, index=True) # e.g. "STANDARD", "EXEMPT", "ZERO_RATED", "SERVICES"
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)


class TaxProfile(Base, TimestampMixin):
    __tablename__ = "tax_profiles"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    default_rate = Column(Numeric(5, 2), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
