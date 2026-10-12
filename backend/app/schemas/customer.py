from pydantic import BaseModel
from typing import Optional


class CustomerBase(BaseModel):
    name: str
    ntn: Optional[str] = None
    strn: Optional[str] = None
    cnic: Optional[str] = None
    registration_type: str = "REGISTERED"
    buyer_type: str = "B2B"
    address: str
    city: str
    province: str
    postal_code: Optional[str] = None
    country: str = "Pakistan"
    phone: Optional[str] = None
    email: Optional[str] = None
    buyer_reference: Optional[str] = None
    is_active: bool = True


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    ntn: Optional[str] = None
    strn: Optional[str] = None
    cnic: Optional[str] = None
    registration_type: Optional[str] = None
    buyer_type: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    buyer_reference: Optional[str] = None
    is_active: Optional[bool] = None


class CustomerResponse(CustomerBase):
    id: str
    tenant_id: str

    class Config:
        from_attributes = True
