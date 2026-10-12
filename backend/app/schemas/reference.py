from pydantic import BaseModel
from typing import Optional
from decimal import Decimal


class HSCodeResponse(BaseModel):
    id: str
    code: str
    description: str
    chapter: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


class UOMResponse(BaseModel):
    id: str
    code: str
    name: str
    fbr_code: str
    is_active: bool

    class Config:
        from_attributes = True


class TaxRateResponse(BaseModel):
    id: str
    name: str
    rate_percent: Decimal
    tax_type: str
    province: str
    sro_reference: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


class SaleTypeResponse(BaseModel):
    id: str
    code: str
    name: str
    description: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


class TaxProfileResponse(BaseModel):
    id: str
    code: str
    name: str
    default_rate: Decimal
    description: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True
