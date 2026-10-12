from pydantic import BaseModel
from typing import Optional, List
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
    tax_rate: Decimal = Decimal("18.00")
    sale_type: str = "STANDARD"
    sro_reference: Optional[str] = None


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
    
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    items: List[InvoiceItemResponse] = []

    class Config:
        from_attributes = True


class InvoiceValidationResult(BaseModel):
    invoice_id: str
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    fbr_ready: bool
