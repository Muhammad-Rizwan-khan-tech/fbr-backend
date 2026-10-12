import enum
from sqlalchemy import Column, String, Numeric, Integer, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.base import generate_uuid, TenantMixin, TimestampMixin, now_utc


class NoteStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    RETRYING = "RETRYING"
    SUBMITTED = "SUBMITTED"
    VALID = "VALID"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class CreditNote(Base, TenantMixin):
    __tablename__ = "credit_notes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    credit_note_number = Column(String(50), nullable=False, index=True)
    original_invoice_id = Column(String(36), ForeignKey("invoices.id"), nullable=False, index=True)
    original_invoice_number = Column(String(50), nullable=False)
    
    note_date = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    reason = Column(String(255), nullable=False)
    buyer_name = Column(String(255), nullable=False)
    buyer_ntn = Column(String(20), nullable=True)
    
    taxable_amount = Column(Numeric(14, 2), default=0.00, nullable=False)
    tax_amount = Column(Numeric(14, 2), default=0.00, nullable=False)
    grand_total = Column(Numeric(14, 2), default=0.00, nullable=False)
    
    status = Column(String(50), default=NoteStatus.DRAFT.value, nullable=False)
    fbr_status = Column(String(50), default="NOT_SUBMITTED", nullable=False)
    fbr_invoice_number = Column(String(100), nullable=True, index=True)
    fbr_reference = Column(String(100), nullable=True)
    fbr_qr_data = Column(Text, nullable=True)
    fbr_submission_date = Column(DateTime(timezone=True), nullable=True)
    fbr_environment = Column(String(20), nullable=True)
    fbr_provider = Column(String(40), nullable=True)
    fbr_is_simulated = Column(Boolean, nullable=False, default=False)
    fbr_error_message = Column(Text, nullable=True)
    correlation_id = Column(String(50), nullable=True, index=True)


class DebitNote(Base, TenantMixin):
    __tablename__ = "debit_notes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    debit_note_number = Column(String(50), nullable=False, index=True)
    original_invoice_id = Column(String(36), ForeignKey("invoices.id"), nullable=False, index=True)
    original_invoice_number = Column(String(50), nullable=False)
    
    note_date = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    reason = Column(String(255), nullable=False)
    buyer_name = Column(String(255), nullable=False)
    buyer_ntn = Column(String(20), nullable=True)
    
    taxable_amount = Column(Numeric(14, 2), default=0.00, nullable=False)
    tax_amount = Column(Numeric(14, 2), default=0.00, nullable=False)
    grand_total = Column(Numeric(14, 2), default=0.00, nullable=False)
    
    status = Column(String(50), default=NoteStatus.DRAFT.value, nullable=False)
    fbr_status = Column(String(50), default="NOT_SUBMITTED", nullable=False)
    fbr_invoice_number = Column(String(100), nullable=True, index=True)
    fbr_reference = Column(String(100), nullable=True)
    fbr_qr_data = Column(Text, nullable=True)
    fbr_submission_date = Column(DateTime(timezone=True), nullable=True)
    fbr_environment = Column(String(20), nullable=True)
    fbr_provider = Column(String(40), nullable=True)
    fbr_is_simulated = Column(Boolean, nullable=False, default=False)
    fbr_error_message = Column(Text, nullable=True)
    correlation_id = Column(String(50), nullable=True, index=True)
