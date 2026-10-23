import io
import json
import uuid
import qrcode
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from fastapi.responses import Response, RedirectResponse
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user, get_current_tenant
from backend.app.core.context import execution_context
from backend.app.models.user import User
from backend.app.models.tenant import Organization
from backend.app.models.invoice import Invoice, InvoiceStatus, FBRSubmissionStatus
from backend.app.models.submission_job import InvoiceSubmissionJob, SubmissionJobStatus
from backend.app.models.document import DocumentType, BackgroundJob, BackgroundJobStatus
from backend.app.models.base import now_utc
from backend.app.schemas.invoice import (
    InvoiceCreate, InvoiceResponse, InvoiceValidationResult
)
from backend.app.schemas.fbr import FBRSubmissionResponse
from backend.app.schemas.submission_job import InvoiceSubmissionJobResponse
from backend.app.schemas.document import DocumentDownloadResponse
from backend.app.services.invoice_service import InvoiceService
from backend.app.services.fbr_service import FBRService
from backend.app.services.audit_service import AuditService
from backend.app.services.document_service import document_service
from backend.app.services.pdf_service import pdf_generator
from backend.app.services.queue_service import queue_service

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.get("", response_model=List[InvoiceResponse])
def list_invoices(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    fbr_status: Optional[str] = Query(None),
    branch_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    query = db.query(Invoice).filter(Invoice.tenant_id == tenant.id)

    if status:
        query = query.filter(Invoice.status == status.upper())
    if fbr_status:
        query = query.filter(Invoice.fbr_status == fbr_status.upper())
    if branch_id:
        query = query.filter(Invoice.branch_id == branch_id)
    if search:
        s = f"%{search}%"
        query = query.filter(
            (Invoice.invoice_number.ilike(s)) |
            (Invoice.buyer_name.ilike(s)) |
            (Invoice.buyer_ntn.ilike(s)) |
            (Invoice.fbr_invoice_number.ilike(s))
        )

    return query.order_by(Invoice.invoice_date.desc()).offset(offset).limit(limit).all()


@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_invoice(
    data: InvoiceCreate,
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    invoice = InvoiceService.create_invoice(
        db=db,
        tenant_id=tenant.id,
        user_id=current_user.id,
        user_email=current_user.email,
        data=data
    )
    from backend.app.services.webhook_service import webhook_service
    webhook_service.dispatch_event(
        db=db,
        tenant_id=tenant.id,
        event_type="invoice.created",
        payload_data={
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "grand_total": float(invoice.grand_total),
        }
    )
    return invoice


@router.post("/validate-draft", response_model=InvoiceValidationResult)
@router.post("/local-validate", response_model=InvoiceValidationResult)
def validate_draft(
    data: InvoiceCreate,
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Validates an unsaved draft invoice against authoritative PRAL rules locally and returns the serialized v1.12 JSON payload."""
    return InvoiceService.validate_draft_invoice(db, tenant_id=tenant.id, data=data)


@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: str,
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.tenant_id == tenant.id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.get("/{invoice_id}/fbr-payload")
def get_invoice_fbr_payload(
    invoice_id: str,
    environment: Optional[str] = Query(None, description="PRODUCTION or SANDBOX"),
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Returns the exact PRAL DI API v1.12 Section 4.1 JSON payload for inspection."""
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.tenant_id == tenant.id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    payload = InvoiceService.serialize_invoice_to_fbr_v112(db, invoice, environment=environment)
    return {
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "environment": (environment or ("SANDBOX" if invoice.scenario_id else "PRODUCTION")).upper(),
        "official_live_verified": False,
        "payload": payload,
    }


@router.post("/{invoice_id}/validate", response_model=InvoiceValidationResult)
@router.post("/{invoice_id}/local-validate", response_model=InvoiceValidationResult)
def validate_invoice(
    invoice_id: str,
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.tenant_id == tenant.id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return InvoiceService.validate_invoice(db, invoice)


@router.post("/{invoice_id}/fbr-validate")
def fbr_validate_invoice_remote(
    invoice_id: str,
    environment: Optional[str] = Query(None, description="Must match the tenant SANDBOX/PRODUCTION mode"),
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Read-only remote FBR/PRAL validation; NEVER registers a tax invoice."""
    from backend.app.core.errors import CredentialsMissingError
    from backend.app.models.tenant import OrganizationSettings
    from backend.app.models.fbr_credential import FBRCredential
    from backend.app.adapters.sandbox_adapter import SandboxFBRAdapter
    from backend.app.adapters.production_adapter import ProductionFBRAdapter

    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id, Invoice.tenant_id == tenant.id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    tenant_settings = db.query(OrganizationSettings).filter(
        OrganizationSettings.organization_id == tenant.id
    ).first()
    active_mode = (tenant_settings.fbr_mode if tenant_settings else "DEMO").upper()
    cred = db.query(FBRCredential).filter(
        FBRCredential.organization_id == tenant.id,
        FBRCredential.is_active.is_(True),
    ).first()
    token = (cred.get_auth_token() or cred.get_api_key()) if cred else None
    if not token:
        raise CredentialsMissingError("The tenant's encrypted FBR token is not configured.")
    if active_mode not in ("SANDBOX", "PRODUCTION"):
        raise HTTPException(status_code=409, detail="Select a real SANDBOX or PRODUCTION gateway mode first.")
    if environment is not None and environment.upper() != active_mode:
        raise HTTPException(
            status_code=409,
            detail="Validation environment does not match the client's configured mode.",
        )
    canonical = FBRService._build_fbr_payload(invoice, db=db)
    if active_mode == "SANDBOX" and not canonical.get("scenarioId"):
        raise HTTPException(status_code=422, detail="Sandbox scenarioId is required for official remote validation.")

    if active_mode == "PRODUCTION":
        adapter = ProductionFBRAdapter(
            bearer_token=token,
            base_url=(tenant_settings.fbr_base_url if tenant_settings else None) or (cred.base_url if cred else None),
        )
    else:
        adapter = SandboxFBRAdapter(
            bearer_token=token,
            base_url=(tenant_settings.fbr_base_url if tenant_settings else None) or (cred.base_url if cred else None),
        )
    result = adapter.validate_invoice_remote(canonical)
    # A validation-only response is never proof of registration/accepted invoice.
    return {
        "invoice_id": invoice.id, "success": result.success,
        "status": result.status, "error_code": result.error_code,
        "error_message": result.error_message, "environment": active_mode,
        "official_validation_passed": bool(result.success),
        "official_live_verified": False,
        "invoice_submitted": False,
        "diagnostics": {
            key: value for key, value in (result.raw_response or {}).items()
            if key in ("http_status", "response_kind", "content_type", "body_chars", "body_sha256_prefix", "gateway_hint", "error_summary")
        },
    }


@router.post("/{invoice_id}/fbr-submit", response_model=FBRSubmissionResponse)
def fbr_submit_invoice_live(
    invoice_id: str,
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Section 4.1/4.2 Live PRAL Invoice Submission (`postinvoicedata_sb` / `postinvoicedata`).
    Strictly requires a configured PRAL Bearer token; never fabricates an official FBR invoice number or QR code when credentials are absent.
    """
    from backend.app.core.errors import CredentialsMissingError, ConflictError
    from backend.app.services.pral_reference_service import pral_reference_service

    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.tenant_id == tenant.id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.fbr_status == FBRSubmissionStatus.VALID.value and not invoice.fbr_is_simulated:
        raise ConflictError(
            f"Invoice {invoice.invoice_number} has already been accepted by FBR ({invoice.fbr_invoice_number}). Duplicate submission blocked."
        )

    token = pral_reference_service.resolve_token(db=db, tenant_id=tenant.id)
    if not token:
        raise CredentialsMissingError(
            "Live FBR invoice submission is disabled because no PRAL Bearer token is configured for this organization. No official FBR invoice number or QR code has been issued."
        )

    return FBRService.submit_invoice(
        db=db,
        invoice=invoice,
        user_id=current_user.id,
        user_email=current_user.email,
    )



@router.post("/{invoice_id}/queue-submit", response_model=InvoiceSubmissionJobResponse, status_code=status.HTTP_202_ACCEPTED)
def queue_submit_to_fbr(
    invoice_id: str,
    scenario: Optional[str] = Query("AUTO", description="Demo simulation scenario: AUTO, VALID, TIMEOUT, REJECTION, PENDING, VALIDATION_ERROR"),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Asynchronously enqueue invoice for FBR submission.
    Returns 202 Accepted with authoritative InvoiceSubmissionJob tracking record.
    Guarantees idempotency via Idempotency-Key header.
    """
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.tenant_id == tenant.id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    job = FBRService.queue_invoice_submission(
        db=db,
        invoice=invoice,
        user_id=current_user.id,
        user_email=current_user.email,
        idempotency_key=idempotency_key,
        forced_scenario=scenario
    )
    return job


@router.get("/{invoice_id}/jobs", response_model=List[InvoiceSubmissionJobResponse])
def get_invoice_submission_jobs(
    invoice_id: str,
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Retrieve full history and retry timeline of FBR submission jobs for this invoice."""
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.tenant_id == tenant.id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return FBRService.list_submission_jobs_for_invoice(db, invoice_id=invoice.id, tenant_id=tenant.id)


@router.get("/{invoice_id}/pdf", response_model=DocumentDownloadResponse)
def get_invoice_pdf(
    invoice_id: str,
    redirect: bool = Query(False, description="If true, 307 redirects to download URL"),
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve or generate official PDF invoice with embedded FBR verification QR code."""
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.tenant_id == tenant.id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    doc = document_service.get_latest_document(
        db=db,
        tenant_id=tenant.id,
        entity_type="INVOICE",
        entity_id=invoice.id,
        document_type=DocumentType.INVOICE_PDF.value
    )

    if not doc:
        # Generate on demand and store
        pdf_bytes = pdf_generator.generate(invoice)
        file_name = f"{invoice.invoice_number}.pdf"
        doc = document_service.store_document(
            db=db,
            tenant_id=tenant.id,
            entity_type="INVOICE",
            entity_id=invoice.id,
            document_type=DocumentType.INVOICE_PDF.value,
            file_name=file_name,
            mime_type="application/pdf",
            data=pdf_bytes,
            created_by=current_user.id,
            is_simulated=bool(invoice.fbr_is_simulated)
        )

    _, signed_url = document_service.generate_download_url(
        db=db,
        document_id=doc.id,
        tenant_id=tenant.id,
        expires_in=600
    )

    if redirect:
        return RedirectResponse(url=signed_url.url, status_code=307)

    return DocumentDownloadResponse(
        document=doc,
        download_url=signed_url.url,
        expires_at=signed_url.expires_at
    )


@router.post("/{invoice_id}/submit", response_model=FBRSubmissionResponse)
def submit_to_fbr(
    invoice_id: str,
    scenario: Optional[str] = Query("AUTO", description="Demo simulation scenario: AUTO, VALID, TIMEOUT, REJECTION, PENDING, VALIDATION_ERROR"),
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.tenant_id == tenant.id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    submission = FBRService.submit_invoice(
        db=db,
        invoice=invoice,
        user_id=current_user.id,
        user_email=current_user.email,
        forced_scenario=scenario
    )
    return submission


@router.get("/{invoice_id}/qr")
def get_invoice_qr_code(
    invoice_id: str,
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.tenant_id == tenant.id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Never manufacture an "official FBR" QR for drafts or failed submissions.
    if invoice.fbr_status != FBRSubmissionStatus.VALID.value:
        raise HTTPException(status_code=409, detail="Invoice has not been accepted by FBR. Verification QR unavailable.")
    qr_text = invoice.fbr_qr_data or invoice.fbr_invoice_number
    if not qr_text:
        raise HTTPException(status_code=409, detail="No verified invoice number or QR payload available.")

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=3,
    )
    qr.add_data(qr_text)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return Response(content=buffer.getvalue(), media_type="image/png", headers={"Cache-Control": "private, no-store"})


class BatchSubmitRequest(BaseModel):
    invoice_ids: List[str]
    scenario: Optional[str] = "AUTO"
    idempotency_key: Optional[str] = None


@router.post("/batch-submit", status_code=status.HTTP_202_ACCEPTED)
def batch_submit_invoices(
    data: BatchSubmitRequest,
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submits a batch of invoices for asynchronous processing by FBR workers."""
    if not data.invoice_ids:
        raise HTTPException(status_code=400, detail="invoice_ids list cannot be empty")

    invoices = db.query(Invoice).filter(
        Invoice.id.in_(data.invoice_ids),
        Invoice.tenant_id == tenant.id
    ).all()

    found_ids = {inv.id for inv in invoices}
    missing_ids = [inv_id for inv_id in data.invoice_ids if inv_id not in found_ids]
    if missing_ids:
        raise HTTPException(status_code=404, detail=f"Invoices not found or not owned by tenant: {missing_ids}")

    already_accepted = [inv for inv in invoices if inv.fbr_status == "VALID" or inv.status == "VALID"]
    in_flight = [inv for inv in invoices if inv.status in ("QUEUED", "SUBMITTING", "RETRYING")]
    eligible = [
        inv for inv in invoices
        if inv not in already_accepted and inv not in in_flight and inv.status != InvoiceStatus.CANCELLED.value
    ]

    if not eligible:
        return {
            "batch_job_id": None,
            "total_submitted": 0,
            "eligible_count": 0,
            "already_accepted_count": len(already_accepted),
            "in_flight_count": len(in_flight),
            "message": "No eligible invoices to submit. Selected invoices are already valid or in-flight.",
        }

    correlation_id = execution_context.correlation_id.get() or f"batch-{uuid.uuid4().hex[:10]}"

    bg_job = BackgroundJob(
        tenant_id=tenant.id,
        job_type="BATCH_FBR_SUBMISSION",
        entity_type="BATCH",
        status=BackgroundJobStatus.QUEUED.value,
        correlation_id=correlation_id,
        enqueued_at=now_utc(),
        created_by=current_user.id,
        params=json.dumps({"total": len(eligible), "invoice_ids": [inv.id for inv in eligible]})
    )
    db.add(bg_job)
    db.flush()

    # Create submission jobs for each eligible invoice
    queued_jobs = []
    for inv in eligible:
        job = FBRService.queue_invoice_submission(
            db=db,
            invoice=inv,
            user_id=current_user.id,
            user_email=current_user.email,
            forced_scenario=data.scenario or "AUTO",
            batch_job_id=bg_job.id,
            auto_dispatch=False, # Worker will process as batch
        )
        queued_jobs.append(job)

    db.commit()

    # Enqueue batch worker task
    queue_service.enqueue_batch_fbr_submission(
        batch_job_id=bg_job.id,
        tenant_id=tenant.id,
        correlation_id=correlation_id,
    )

    return {
        "batch_job_id": bg_job.id,
        "total_submitted": len(eligible),
        "eligible_count": len(eligible),
        "already_accepted_count": len(already_accepted),
        "in_flight_count": len(in_flight),
        "correlation_id": correlation_id,
        "queued_invoice_ids": [inv.id for inv in eligible],
        "message": f"Successfully queued {len(eligible)} invoices for bulk FBR submission.",
    }


@router.get("/batch-jobs/{job_id}")
def get_batch_job_status(
    job_id: str,
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Polls real-time progress and item statuses of a bulk submission batch."""
    bg_job = db.query(BackgroundJob).filter(
        BackgroundJob.id == job_id,
        BackgroundJob.tenant_id == tenant.id
    ).first()
    if not bg_job:
        raise HTTPException(status_code=404, detail="Batch job not found")

    submission_jobs = db.query(InvoiceSubmissionJob).filter(
        InvoiceSubmissionJob.batch_job_id == job_id,
        InvoiceSubmissionJob.tenant_id == tenant.id
    ).all()

    total = len(submission_jobs)
    succeeded = len([j for j in submission_jobs if j.status == "ACCEPTED"])
    failed = len([j for j in submission_jobs if j.status in ("FAILED", "REJECTED")])
    in_flight = len([j for j in submission_jobs if j.status in ("QUEUED", "PROCESSING", "SUBMITTED", "RETRYING")])
    progress = int(((succeeded + failed) / total) * 100) if total > 0 else 100

    items = []
    for j in submission_jobs:
        inv = db.query(Invoice).filter(Invoice.id == j.invoice_id).first()
        items.append({
            "job_id": j.id,
            "invoice_id": j.invoice_id,
            "invoice_number": inv.invoice_number if inv else "Unknown",
            "status": j.status,
            "fbr_reference": j.fbr_reference,
            "last_error_message": j.last_error_message,
        })

    return {
        "job_id": bg_job.id,
        "status": bg_job.status,
        "total": total,
        "succeeded": succeeded,
        "failed": failed,
        "in_flight": in_flight,
        "progress_percentage": progress,
        "completed": in_flight == 0 and total > 0,
        "enqueued_at": bg_job.enqueued_at,
        "completed_at": bg_job.completed_at,
        "items": items,
    }


@router.post("/reconcile-fbr")
def reconcile_fbr_invoices(
    invoice_ids: Optional[List[str]] = None,
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Reconciles local invoice FBR statuses against the active FBR ledger."""
    query = db.query(Invoice).filter(Invoice.tenant_id == tenant.id)
    if invoice_ids:
        query = query.filter(Invoice.id.in_(invoice_ids))
    else:
        query = query.filter(Invoice.status.in_(["SUBMITTED", "QUEUED", "SUBMITTING"]))

    invoices = query.all()
    reconciled = 0
    results = []

    for inv in invoices:
        # Check latest submission job
        latest_job = db.query(InvoiceSubmissionJob).filter(
            InvoiceSubmissionJob.invoice_id == inv.id,
            InvoiceSubmissionJob.tenant_id == tenant.id
        ).order_by(InvoiceSubmissionJob.created_at.desc()).first()

        if latest_job and latest_job.status == "ACCEPTED":
            inv.status = InvoiceStatus.VALID.value
            inv.fbr_status = FBRSubmissionStatus.VALID.value
            reconciled += 1
        results.append({
            "invoice_id": inv.id,
            "invoice_number": inv.invoice_number,
            "current_status": inv.status,
            "fbr_status": inv.fbr_status,
        })

    db.commit()
    return {
        "reconciled_count": reconciled,
        "checked_count": len(invoices),
        "results": results,
    }
