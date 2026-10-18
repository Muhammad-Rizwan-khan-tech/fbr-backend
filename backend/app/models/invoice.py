import enum
from sqlalchemy import Column, String, Boolean, Numeric, Integer, DateTime, Date, ForeignKey, Text, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.base import generate_uuid, TenantMixin, TimestampMixin, now_utc


class InvoiceStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    VALIDATING = "VALIDATING"
    INVALID = "INVALID"
    READY = "READY"
    QUEUED = "QUEUED"          # submission job persisted, waiting for a worker
    SUBMITTING = "SUBMITTING"  # worker is talking to the FBR adapter
    RETRYING = "RETRYING"      # transient failure, retry scheduled
    SUBMITTED = "SUBMITTED"    # provider accepted for asynchronous verification
    VALID = "VALID"            # accepted by FBR (job status ACCEPTED)
    REJECTED = "REJECTED"      # rejected by FBR (permanent)
    FAILED = "FAILED"          # technical failure, retries exhausted
    CANCELLED = "CANCELLED"


class FBRSubmissionStatus(str, enum.Enum):
    NOT_SUBMITTED = "NOT_SUBMITTED"
    PENDING = "PENDING"
    VALID = "VALID"
    INVALID = "INVALID"
    FAILED = "FAILED"


class Invoice(Base, TenantMixin):
    __tablename__ = "invoices"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    
    # Association
    branch_id = Column(String(36), ForeignKey("branches.id"), nullable=False, index=True)
    customer_id = Column(String(36), ForeignKey("customers.id"), nullable=False, index=True)
    
    # Identification
    invoice_number = Column(String(50), nullable=False, index=True) # Generated server-side
    invoice_type = Column(String(50), default="TAX_INVOICE", nullable=False)
    invoice_date = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=True)
    
    # Snapshot of Seller & Buyer at time of invoice
    seller_name = Column(String(255), nullable=False)
    seller_ntn = Column(String(20), nullable=False)
    seller_strn = Column(String(30), nullable=True)
    seller_branch_code = Column(String(50), nullable=False)
    seller_province = Column(String(100), nullable=False)
    
    buyer_name = Column(String(255), nullable=False)
    buyer_ntn = Column(String(20), nullable=True)
    buyer_strn = Column(String(30), nullable=True)
    buyer_cnic = Column(String(20), nullable=True)
    buyer_registration_type = Column(String(50), default="REGISTERED", nullable=False)
    buyer_address = Column(Text, nullable=False)
    buyer_province = Column(String(100), nullable=False)
    
    # Invoice Financial Totals
    subtotal = Column(Numeric(14, 2), default=0.00, nullable=False) # Gross line amount
    total_discount = Column(Numeric(14, 2), default=0.00, nullable=False)
    taxable_amount = Column(Numeric(14, 2), default=0.00, nullable=False)
    total_tax = Column(Numeric(14, 2), default=0.00, nullable=False)
    other_charges = Column(Numeric(14, 2), default=0.00, nullable=False)
    grand_total = Column(Numeric(14, 2), default=0.00, nullable=False)
    
    # Lifecycle Status
    status = Column(String(50), default=InvoiceStatus.DRAFT.value, nullable=False, index=True)
    
    # FBR Integration Snapshot
    fbr_status = Column(String(50), default=FBRSubmissionStatus.NOT_SUBMITTED.value, nullable=False, index=True)
    fbr_invoice_number = Column(String(100), nullable=True, index=True)
    fbr_qr_data = Column(Text, nullable=True)
    fbr_submission_date = Column(DateTime(timezone=True), nullable=True)
    fbr_error_code = Column(String(50), nullable=True)
    fbr_error_message = Column(Text, nullable=True)
    # Provenance of the FBR data above. Simulated (DEMO/MOCK) data must never look genuine.
    fbr_environment = Column(String(20), nullable=True)   # DEMO | SANDBOX | PRODUCTION
    fbr_provider = Column(String(40), nullable=True)      # MOCK | SANDBOX | LICENSED_INTEGRATOR | PRODUCTION
    fbr_is_simulated = Column(Boolean, nullable=False, default=False)
    
    # References and Notes
    reference_number = Column(String(100), nullable=True)
    scenario_id = Column(String(20), nullable=True)
    payment_terms = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    correlation_id = Column(String(50), nullable=True, index=True)  # traces request -> job -> worker -> FBR

    __table_args__ = (
        # DB-level guarantee that a tenant can never hold two invoices with the same number.
        UniqueConstraint("tenant_id", "invoice_number", name="uq_invoices_tenant_invoice_number"),
    )

    # Relationships
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan", order_by="InvoiceItem.item_seq")
    submissions = relationship("FBRSubmission", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceItem(Base, TimestampMixin):
    __tablename__ = "invoice_items"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    invoice_id = Column(String(36), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=True)
    
    item_seq = Column(Integer, default=1, nullable=False)
    item_code = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    hs_code = Column(String(20), nullable=False) # Pakistan HS code e.g. 8471.30.10
    
    quantity = Column(Numeric(12, 3), default=1.000, nullable=False)
    uom = Column(String(60), default="NOS", nullable=False)
    unit_price = Column(Numeric(14, 2), default=0.00, nullable=False)
    gross_amount = Column(Numeric(14, 2), default=0.00, nullable=False)
    discount = Column(Numeric(14, 2), default=0.00, nullable=False)
    taxable_amount = Column(Numeric(14, 2), default=0.00, nullable=False)
    
    tax_rate = Column(Numeric(5, 2), default=18.00, nullable=False) # standard 18%
    rate_desc = Column(String(120), nullable=True) # exact PRAL ratE_DESC e.g. "18%", "Exempt", "18% along with..."
    tax_amount = Column(Numeric(14, 2), default=0.00, nullable=False)
    fixed_notified_value_or_retail_price = Column(Numeric(14, 2), default=0.00, nullable=False)
    sales_tax_withheld_at_source = Column(Numeric(14, 2), default=0.00, nullable=False)
    extra_tax = Column(Numeric(14, 2), default=0.00, nullable=False)
    further_tax = Column(Numeric(14, 2), default=0.00, nullable=False)
    fed_payable = Column(Numeric(14, 2), default=0.00, nullable=False)
    line_total = Column(Numeric(14, 2), default=0.00, nullable=False)
    
    sale_type = Column(String(120), default="STANDARD", nullable=False)
    sro_reference = Column(String(120), nullable=True)
    sro_item_serial_no = Column(String(100), nullable=True)

    invoice = relationship("Invoice", back_populates="items")

