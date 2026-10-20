from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class OrganizationSettingsBase(BaseModel):
    invoice_prefix: str = "INV"
    next_invoice_number: int = 1001
    credit_note_prefix: str = "CRN"
    debit_note_prefix: str = "DBN"
    default_terms: Optional[str] = None
    fbr_mode: str = "DEMO"
    enable_auto_submit: bool = False
    fbr_pos_id: Optional[str] = None
    fbr_api_token: Optional[str] = None
    fbr_base_url: Optional[str] = None


class OrganizationSettingsUpdate(BaseModel):
    invoice_prefix: Optional[str] = None
    next_invoice_number: Optional[int] = None
    credit_note_prefix: Optional[str] = None
    debit_note_prefix: Optional[str] = None
    default_terms: Optional[str] = None
    fbr_mode: Optional[str] = None
    enable_auto_submit: Optional[bool] = None
    fbr_pos_id: Optional[str] = None
    fbr_api_token: Optional[str] = None
    fbr_base_url: Optional[str] = None


class OrganizationSettingsResponse(OrganizationSettingsBase):
    id: str
    organization_id: str
    fbr_api_token: Optional[str] = Field(default=None, exclude=True, repr=False)

    class Config:
        from_attributes = True


class TaxpayerBase(BaseModel):
    legal_name: str
    trade_name: Optional[str] = None
    ntn: str
    strn: Optional[str] = None
    registration_type: str = "REGISTERED"
    business_type: str = "WHOLESALER"
    address: str
    city: str
    province: str
    postal_code: Optional[str] = None
    country: str = "Pakistan"
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    authorized_signatory_name: Optional[str] = None
    authorized_signatory_designation: Optional[str] = None


class TaxpayerCreate(TaxpayerBase):
    pass


class TaxpayerUpdate(BaseModel):
    legal_name: Optional[str] = None
    trade_name: Optional[str] = None
    ntn: Optional[str] = None
    strn: Optional[str] = None
    registration_type: Optional[str] = None
    business_type: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    authorized_signatory_name: Optional[str] = None
    authorized_signatory_designation: Optional[str] = None


class TaxpayerResponse(TaxpayerBase):
    id: str
    tenant_id: str

    class Config:
        from_attributes = True


class BranchBase(BaseModel):
    branch_name: str
    branch_code: str
    fbr_pos_id: Optional[str] = None
    address: str
    city: str
    province: str
    phone: Optional[str] = None
    email: Optional[str] = None
    is_active: bool = True
    is_main: bool = False


class BranchCreate(BranchBase):
    pass


class BranchUpdate(BaseModel):
    branch_name: Optional[str] = None
    branch_code: Optional[str] = None
    fbr_pos_id: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None
    is_main: Optional[bool] = None


class BranchResponse(BranchBase):
    id: str
    tenant_id: str

    class Config:
        from_attributes = True


class OrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    status: str
    is_active: bool
    settings: Optional[OrganizationSettingsResponse] = None
    taxpayer: Optional[TaxpayerResponse] = None
    branches: List[BranchResponse] = []

    class Config:
        from_attributes = True
