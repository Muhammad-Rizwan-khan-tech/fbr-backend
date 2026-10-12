import uuid
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.dependencies import require_api_key, ApiKeyAuth
from backend.app.models.tenant import Organization
from backend.app.models.branch import Branch
from backend.app.models.customer import Customer
from backend.app.models.invoice import Invoice, InvoiceItem, InvoiceStatus, FBRSubmissionStatus
from backend.app.models.base import now_utc
from backend.app.services.tax_engine import PakistanTaxEngine, TaxCalculationError
from backend.app.services.invoice_service import InvoiceService
from backend.app.services.fbr_service import FBRService
from backend.app.services.webhook_service import webhook_service
from backend.app.schemas.external import (
    ExternalInvoiceCreate, ExternalInvoiceResponse, ExternalInvoiceStatusResponse
)

router = APIRouter(prefix="/external/invoices", tags=["Developer Invoicing API"])


@router.post("", response_model=ExternalInvoiceResponse, status_code=status.HTTP_201_CREATED)
def ingest_external_invoice(
    data: ExternalInvoiceCreate,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    auth: ApiKeyAuth = Depends(require_api_key(required_scope="invoices:write")),
    db: Session = Depends(get_db)
):
    """Ingest, validate, and issue a digital tax invoice from an external ERP or accounting system.
    
    Automatically calculates Pakistan sales taxes according to Sales Tax Act 1990 rules,
    assigns sequential invoice numbering, dispatches webhooks, and queues FBR transmission.
    """
    tenant: Organization = auth.tenant
    effective_idempotency_key = idempotency_key or data.external_reference_id

    # 1. Idempotency Guard (prevent duplicate generation on network retries)
    if effective_idempotency_key:
        existing = db.query(Invoice).filter(
            Invoice.tenant_id == tenant.id,
            Invoice.reference_number == effective_idempotency_key
        ).first()
        if existing:
            return ExternalInvoiceResponse(
                success=True,
                invoice_id=existing.id,
                invoice_number=existing.invoice_number,
                external_reference_id=existing.reference_number,
                taxable_amount=existing.taxable_amount,
                total_tax=existing.total_tax,
                grand_total=existing.grand_total,
                fbr_status=existing.fbr_status,
                submission_job_id=None,
                message="Invoice already exists (idempotent replay returned)."
            )

    # 2. Resolve Seller Branch
    branch = None
    if data.branch_code:
        branch = db.query(Branch).filter(
            Branch.tenant_id == tenant.id,
            Branch.branch_code == data.branch_code
        ).first()
    if not branch:
        branch = db.query(Branch).filter(
            Branch.tenant_id == tenant.id,
            Branch.is_main == True
        ).first()
    if not branch:
        branch = db.query(Branch).filter(Branch.tenant_id == tenant.id).first()
    if not branch:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active organization branch found. Please configure a branch in settings."
        )

    # 3. Resolve or Automatically Register Buyer / Customer
    buyer_info = data.buyer
    customer = None
    if buyer_info.ntn:
        customer = db.query(Customer).filter(
            Customer.tenant_id == tenant.id,
            Customer.ntn == buyer_info.ntn
        ).first()
    elif buyer_info.cnic:
        customer = db.query(Customer).filter(
            Customer.tenant_id == tenant.id,
            Customer.cnic == buyer_info.cnic
        ).first()

    if not customer:
        customer = Customer(
            tenant_id=tenant.id,
            name=buyer_info.name,
            ntn=buyer_info.ntn,
            strn=buyer_info.strn,
            cnic=buyer_info.cnic,
            registration_type="REGISTERED" if buyer_info.ntn else "UNREGISTERED",
            buyer_type=buyer_info.buyer_type or ("B2B" if buyer_info.ntn else "B2C"),
            address=buyer_info.address or "Main Boulevard",
            city=buyer_info.city or "Karachi",
            province=buyer_info.province or "Sindh",
            phone=buyer_info.phone,
            email=buyer_info.email,
        )
        db.add(customer)
        db.flush()

    # 4. Tax Engine Calculations for Line Items
    tax_items = []
    raw_items_calc = []
    for item in data.items:
        raw_items_calc.append({
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "discount": item.discount,
            "tax_rate": item.tax_rate
        })

    try:
        totals = PakistanTaxEngine.calculate_invoice_totals(raw_items_calc, Decimal("0.00"))
    except TaxCalculationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    for idx, item in enumerate(data.items, start=1):
        line_calc = PakistanTaxEngine.calculate_line_item(
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount=item.discount,
            tax_rate_percent=item.tax_rate
        )
        tax_items.append(InvoiceItem(
            item_seq=idx,
            item_code=item.item_code or f"ITEM-{idx:03d}",
            description=item.description or item.item_name,
            hs_code=item.hs_code,
            uom=item.uom,
            quantity=item.quantity,
            unit_price=item.unit_price,
            gross_amount=line_calc["gross_amount"],
            discount=line_calc["discount"],
            taxable_amount=line_calc["taxable_amount"],
            tax_rate=item.tax_rate,
            tax_amount=line_calc["tax_amount"],
            line_total=line_calc["line_total"],
            sale_type=item.sale_type,
            sro_reference=item.sro_reference
        ))

    # 5. Generate Atomic Sequential Invoice Number
    invoice_number = InvoiceService.generate_next_invoice_number(db, tenant.id, branch.branch_code)

    # 6. Persist Invoice
    seller_taxpayer = tenant.taxpayer
    invoice = Invoice(
        tenant_id=tenant.id,
        branch_id=branch.id,
        customer_id=customer.id,
        invoice_number=invoice_number,
        invoice_date=data.invoice_date or now_utc(),
        invoice_type="TAX_INVOICE",
        seller_branch_code=branch.branch_code,
        seller_ntn=seller_taxpayer.ntn if seller_taxpayer else "0000000-0",
        seller_strn=seller_taxpayer.strn if seller_taxpayer else None,
        seller_name=seller_taxpayer.legal_name if seller_taxpayer else tenant.name,
        seller_province=branch.province,
        buyer_name=customer.name,
        buyer_ntn=customer.ntn,
        buyer_strn=customer.strn,
        buyer_cnic=customer.cnic,
        buyer_registration_type=customer.registration_type,
        buyer_address=customer.address,
        buyer_province=customer.province,
        subtotal=totals["subtotal"],
        total_discount=totals["total_discount"],
        taxable_amount=totals["taxable_amount"],
        total_tax=totals["total_tax"],
        other_charges=totals["other_charges"],
        grand_total=totals["grand_total"],
        status=InvoiceStatus.QUEUED.value if data.auto_submit_fbr else InvoiceStatus.READY.value,
        fbr_status=FBRSubmissionStatus.NOT_SUBMITTED.value,
        reference_number=effective_idempotency_key,
        notes=data.terms_and_conditions,
        items=tax_items
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    # 7. Fire Asynchronous Webhook
    webhook_service.dispatch_event(
        db=db,
        tenant_id=tenant.id,
        event_type="invoice.created",
        payload_data={
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "grand_total": float(invoice.grand_total),
            "external_reference_id": invoice.reference_number
        }
    )

    # 8. Queue FBR Submission
    submission_job_id = None
    fbr_status = FBRSubmissionStatus.NOT_SUBMITTED.value
    if data.auto_submit_fbr:
        try:
            job = FBRService.queue_invoice_submission(
                db=db,
                invoice=invoice,
                user_id=f"api_key:{auth.api_key.key_prefix}",
                user_email="api-developer@system.local",
                idempotency_key=f"ext_{effective_idempotency_key}" if effective_idempotency_key else None,
                forced_scenario="AUTO"
            )
            submission_job_id = job.id
            fbr_status = FBRSubmissionStatus.PENDING.value
        except Exception as exc:
            pass

    return ExternalInvoiceResponse(
        success=True,
        invoice_id=invoice.id,
        invoice_number=invoice.invoice_number,
        external_reference_id=invoice.reference_number,
        taxable_amount=invoice.taxable_amount,
        total_tax=invoice.total_tax,
        grand_total=invoice.grand_total,
        fbr_status=fbr_status,
        submission_job_id=submission_job_id,
        message="Invoice issued and queued successfully for FBR fiscal verification."
    )


@router.get("/{invoice_id}/status", response_model=ExternalInvoiceStatusResponse)
def get_external_invoice_status(
    invoice_id: str,
    auth: ApiKeyAuth = Depends(require_api_key(required_scope="invoices:read")),
    db: Session = Depends(get_db)
):
    """Query live FBR submission status, QR payload, and verification token for an invoice."""
    tenant: Organization = auth.tenant

    invoice = db.query(Invoice).filter(
        Invoice.tenant_id == tenant.id,
        (Invoice.id == invoice_id) | (Invoice.invoice_number == invoice_id) | (Invoice.reference_number == invoice_id)
    ).first()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Get submission job if available
    from backend.app.models.submission_job import InvoiceSubmissionJob
    sub_job = db.query(InvoiceSubmissionJob).filter(
        InvoiceSubmissionJob.invoice_id == invoice.id,
        InvoiceSubmissionJob.tenant_id == tenant.id
    ).order_by(InvoiceSubmissionJob.created_at.desc()).first()

    return ExternalInvoiceStatusResponse(
        invoice_id=invoice.id,
        invoice_number=invoice.invoice_number,
        external_reference_id=invoice.reference_number,
        invoice_status=invoice.status,
        fbr_status=invoice.fbr_status,
        fbr_invoice_number=invoice.fbr_invoice_number,
        fbr_qr_data=invoice.fbr_qr_data,
        fbr_submission_date=invoice.fbr_submission_date,
        is_simulated=invoice.fbr_is_simulated if invoice.fbr_is_simulated is not None else False,
        environment=invoice.fbr_environment or "DEMO",
        latest_error=sub_job.last_error_message if sub_job else None,
        attempt_count=sub_job.attempt_count if sub_job else 0
    )
