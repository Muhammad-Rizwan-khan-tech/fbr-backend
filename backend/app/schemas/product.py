from pydantic import BaseModel
from typing import Optional
from decimal import Decimal


class ProductBase(BaseModel):
    item_code: str
    name: str
    description: Optional[str] = None
    hs_code: str
    uom: str = "NOS"
    sale_type: str = "STANDARD"
    tax_rate: Decimal = Decimal("18.00")
    sro_reference: Optional[str] = None
    unit_price: Decimal
    is_active: bool = True


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    item_code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    hs_code: Optional[str] = None
    uom: Optional[str] = None
    sale_type: Optional[str] = None
    tax_rate: Optional[Decimal] = None
    sro_reference: Optional[str] = None
    unit_price: Optional[Decimal] = None
    is_active: Optional[bool] = None


class ProductResponse(ProductBase):
    id: str
    tenant_id: str

    class Config:
        from_attributes = True
