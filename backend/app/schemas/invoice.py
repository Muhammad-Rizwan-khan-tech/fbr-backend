from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal


class InvoiceItemCreate(BaseModel):
    product_id: Optional[str] = None
    item_code: str
    description: str
    hs_code: str
    quantity: Decimal
    uom: str = "NOS"
    unit_price: Decimal
    discount: Decimal = Decimal("0.00")
    tax_rate: Decimal = Field(..., ge=0, description="Applicable sales tax rate percent (e.g. 0.00, 15.00, 18.00)")
    rate_desc: Optional[str] = None  # Exact PRAL ratE_DESC e.g. "18%", "Exempt", "18% along with..."
    fixed_notified_value_or_retail_price: Decimal = Decimal("0.00")
    sales_tax_withheld_at_source: Decimal = Decimal("0.00")
    extra_tax: Decimal = Decimal("0.00")
    further_tax: Decimal = Decimal("0.00")
    fed_payable: Decimal = Decimal("0.00")
    sale_type: str = "STANDARD"
    sro_reference: Optional[str] = None
    sro_item_serial_no: Optional[str] = None


class InvoiceItemResponse(InvoiceItemCreate):
    id: str
    item_seq: int
    gross_amount: Decimal
    taxable_amount: Decimal
    tax_amount: Decimal
    line_total: Decimal

    class Config:
        from_attributes = True


class InvoiceCreate(BaseModel):
    branch_id: str
    customer_id: str
    invoice_type: str = "TAX_INVOICE"
    invoice_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    reference_number: Optional[str] = None
    scenario_id: Optional[str] = None
    payment_terms: Optional[str] = None
    notes: Optional[str] = None
    other_charges: Decimal = Decimal("0.00")
    items: List[InvoiceItemCreate]


class InvoiceUpdate(BaseModel):
    branch_id: Optional[str] = None
    customer_id: Optional[str] = None
    invoice_type: Optional[str] = None
    due_date: Optional[datetime] = None
    reference_number: Optional[str] = None
    scenario_id: Optional[str] = None
    payment_terms: Optional[str] = None
    notes: Optional[str] = None
    other_charges: Optional[Decimal] = None
    items: Optional[List[InvoiceItemCreate]] = None


class InvoiceResponse(BaseModel):
    id: str
    tenant_id: str
    branch_id: str
    customer_id: str
    invoice_number: str
    invoice_type: str
    invoice_date: datetime
    due_date: Optional[datetime] = None

    seller_name: str
    seller_ntn: str
    seller_strn: Optional[str] = None
    seller_branch_code: str
    seller_province: str

    buyer_name: str
    buyer_ntn: Optional[str] = None
    buyer_strn: Optional[str] = None
    buyer_cnic: Optional[str] = None
    buyer_registration_type: str
    buyer_address: str
    buyer_province: str

    subtotal: Decimal
    total_discount: Decimal
    taxable_amount: Decimal
    total_tax: Decimal
    other_charges: Decimal
    grand_total: Decimal

    status: str
    fbr_status: str
    fbr_invoice_number: Optional[str] = None
    fbr_qr_data: Optional[str] = None
    fbr_submission_date: Optional[datetime] = None
    fbr_error_code: Optional[str] = None
    fbr_error_message: Optional[str] = None
    fbr_environment: Optional[str] = None
    fbr_provider: Optional[str] = None
    fbr_is_simulated: Optional[bool] = False

    reference_number: Optional[str] = None
    scenario_id: Optional[str] = None
    notes: Optional[str] = None
    items: List[InvoiceItemResponse] = []

    class Config:
        from_attributes = True


class InvoiceValidationResult(BaseModel):
    invoice_id: Optional[str] = None
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    line_item_errors: List[Dict[str, Any]] = Field(default_factory=list)
    structured_errors: List[Dict[str, Any]] = Field(default_factory=list)
    pral_status: Optional[str] = None
    fbr_ready: bool
    official_live_verified: bool = False
    serialized_fbr_payload: Optional[Dict[str, Any]] = None
