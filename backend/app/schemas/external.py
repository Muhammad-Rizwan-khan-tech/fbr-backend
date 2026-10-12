from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ExternalBuyerInfo(BaseModel):
    name: str = Field(..., min_length=2, max_length=200, description="Customer / Buyer legal or trading name")
    ntn: Optional[str] = Field(None, description="National Tax Number (e.g. '1234567-8')")
    strn: Optional[str] = Field(None, description="Sales Tax Registration Number")
    cnic: Optional[str] = Field(None, description="National Identity Card # if unregistered consumer")
    buyer_type: Optional[str] = Field(None, description="REGISTERED_BUSINESS | UNREGISTERED_CONSUMER | GOVERNMENT | EXPORTER")
    address: str = Field("Main Boulevard", description="Physical street address")
    city: str = Field("Karachi", description="City")
    province: str = Field("Sindh", description="Province")
    phone: Optional[str] = None
    email: Optional[str] = None


class ExternalInvoiceItem(BaseModel):
    item_code: Optional[str] = Field(None, description="ERP internal product code")
    item_name: str = Field(..., min_length=2, max_length=200, description="Product / Item name")
    description: Optional[str] = None
    hs_code: str = Field(..., min_length=4, max_length=16, description="Pakistan Customs Tariff HS Code (e.g. '8471.30.10')")
    uom: str = Field("NUM", description="Unit of Measure (NUM, KGS, MTR, LTR, etc.)")
    quantity: Decimal = Field(..., gt=0, description="Quantity")
    unit_price: Decimal = Field(..., ge=0, description="Price per unit before tax and discounts")
    discount: Decimal = Field(Decimal("0.00"), ge=0, description="Discount amount")
    tax_rate: Decimal = Field(Decimal("18.00"), ge=0, le=100, description="Sales tax rate percentage (default: 18.00)")
    sale_type: str = Field("GOODS", description="GOODS | SERVICES | RAW_MATERIALS | CAPITAL_GOODS")
    sro_reference: Optional[str] = None


class ExternalInvoiceCreate(BaseModel):
    branch_code: Optional[str] = Field(None, description="Branch identifier; defaults to organization main branch")
    invoice_date: Optional[date] = Field(None, description="Invoice date; defaults to today")
    external_reference_id: Optional[str] = Field(None, max_length=100, description="ERP internal reference/invoice ID for idempotency")
    buyer: ExternalBuyerInfo
    items: List[ExternalInvoiceItem] = Field(..., min_length=1, description="Line items list")
    payment_mode: str = Field("BANK_TRANSFER", description="CASH | BANK_TRANSFER | CREDIT | CHEQUE | ONLINE")
    terms_and_conditions: Optional[str] = None
    auto_submit_fbr: bool = Field(True, description="Immediately queue for FBR fiscal transmission")


class ExternalInvoiceResponse(BaseModel):
    success: bool
    invoice_id: str
    invoice_number: str
    external_reference_id: Optional[str] = None
    taxable_amount: Decimal
    total_tax: Decimal
    grand_total: Decimal
    fbr_status: str  # QUEUED | NOT_SUBMITTED | VALID | FAILED
    submission_job_id: Optional[str] = None
    message: str


class ExternalInvoiceStatusResponse(BaseModel):
    invoice_id: str
    invoice_number: str
    external_reference_id: Optional[str] = None
    invoice_status: str
    fbr_status: str
    fbr_invoice_number: Optional[str] = None
    fbr_qr_data: Optional[str] = None
    fbr_submission_date: Optional[datetime] = None
    is_simulated: bool
    environment: str
    latest_error: Optional[str] = None
    attempt_count: int
