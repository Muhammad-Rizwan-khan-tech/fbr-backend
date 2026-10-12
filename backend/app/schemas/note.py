from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from decimal import Decimal


class CreditNoteCreate(BaseModel):
    original_invoice_id: str
    reason: str
    taxable_amount: Decimal
    tax_amount: Decimal
    grand_total: Decimal


class CreditNoteResponse(BaseModel):
    id: str
    tenant_id: str
    credit_note_number: str
    original_invoice_id: str
    original_invoice_number: str
    note_date: datetime
    reason: str
    buyer_name: str
    buyer_ntn: Optional[str] = None
    taxable_amount: Decimal
    tax_amount: Decimal
    grand_total: Decimal
    status: str
    fbr_status: str
    fbr_reference: Optional[str] = None
    fbr_invoice_number: Optional[str] = None
    fbr_qr_data: Optional[str] = None
    fbr_submission_date: Optional[datetime] = None
    fbr_environment: Optional[str] = None
    fbr_provider: Optional[str] = None
    fbr_is_simulated: bool = False
    fbr_error_message: Optional[str] = None
    correlation_id: Optional[str] = None

    class Config:
        from_attributes = True


class DebitNoteCreate(BaseModel):
    original_invoice_id: str
    reason: str
    taxable_amount: Decimal
    tax_amount: Decimal
    grand_total: Decimal


class DebitNoteResponse(BaseModel):
    id: str
    tenant_id: str
    debit_note_number: str
    original_invoice_id: str
    original_invoice_number: str
    note_date: datetime
    reason: str
    buyer_name: str
    buyer_ntn: Optional[str] = None
    taxable_amount: Decimal
    tax_amount: Decimal
    grand_total: Decimal
    status: str
    fbr_status: str
    fbr_reference: Optional[str] = None
    fbr_invoice_number: Optional[str] = None
    fbr_qr_data: Optional[str] = None
    fbr_submission_date: Optional[datetime] = None
    fbr_environment: Optional[str] = None
    fbr_provider: Optional[str] = None
    fbr_is_simulated: bool = False
    fbr_error_message: Optional[str] = None
    correlation_id: Optional[str] = None

    class Config:
        from_attributes = True
