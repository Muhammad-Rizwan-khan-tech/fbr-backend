import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user, get_current_tenant
from backend.app.core.context import execution_context
from backend.app.models.user import User
from backend.app.models.tenant import Organization, OrganizationSettings
from backend.app.models.taxpayer import Taxpayer
from backend.app.models.invoice import Invoice, InvoiceStatus
from backend.app.models.note import CreditNote, DebitNote, NoteStatus
from backend.app.models.document import DocumentType
from backend.app.schemas.note import (
    CreditNoteCreate, CreditNoteResponse, DebitNoteCreate, DebitNoteResponse
)
from backend.app.schemas.document import DocumentDownloadResponse, DocumentResponse
from backend.app.services.audit_service import AuditService
from backend.app.services.queue_service import queue_service
from backend.app.services.pdf_service import pdf_generator
from backend.app.services.document_service import document_service

router = APIRouter(tags=["Credit & Debit Notes"])


@router.get("/credit-notes", response_model=List[CreditNoteResponse])
def list_credit_notes(
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    return db.query(CreditNote).filter(CreditNote.tenant_id == tenant.id).order_by(CreditNote.note_date.desc()).all()


@router.get("/credit-notes/reconciliation/{invoice_id}")
def get_invoice_credit_reconciliation(
    invoice_id: str,
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Returns real-time credit reconciliation limits and remaining creditable balance for an invoice."""
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.tenant_id == tenant.id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    existing_notes = db.query(CreditNote).filter(
        CreditNote.original_invoice_id == invoice.id,
        CreditNote.tenant_id == tenant.id,
        CreditNote.status != NoteStatus.CANCELLED.value,
    ).all()

    total_credited = sum(Decimal(str(n.grand_total)) for n in existing_notes)
    inv_total = Decimal(str(invoice.grand_total))
    remaining = max(Decimal("0.00"), inv_total - total_credited)

    return {
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "invoice_date": invoice.invoice_date,
        "invoice_status": invoice.status,
        "fbr_status": invoice.fbr_status,
        "fbr_invoice_number": invoice.fbr_invoice_number,
        "grand_total": float(inv_total),
        "total_credited": float(total_credited),
        "remaining_creditable_balance": float(remaining),
        "credit_notes_count": len(existing_notes),
        "is_fully_credited": remaining <= Decimal("0.00"),
    }


@router.post("/credit-notes", response_model=CreditNoteResponse)
def create_credit_note(
    data: CreditNoteCreate,
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    invoice = db.query(Invoice).filter(
        Invoice.id == data.original_invoice_id,
        Invoice.tenant_id == tenant.id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Original invoice not found")

    if invoice.status in (InvoiceStatus.CANCELLED.value, InvoiceStatus.DRAFT.value):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot issue a Credit Note against an invoice in '{invoice.status}' status."
        )

    # Reconciliation check: cumulative credit cannot exceed original invoice grand total
    existing_notes = db.query(CreditNote).filter(
        CreditNote.original_invoice_id == invoice.id,
        CreditNote.tenant_id == tenant.id,
        CreditNote.status != NoteStatus.CANCELLED.value,
    ).all()
    already_credited = sum(Decimal(str(n.grand_total)) for n in existing_notes)
    inv_total = Decimal(str(invoice.grand_total))
    remaining_balance = inv_total - already_credited

    new_total = Decimal(str(data.grand_total))
    if new_total > remaining_balance:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Credit Note amount (PKR {new_total:,.2f}) exceeds remaining creditable balance "
                f"(PKR {remaining_balance:,.2f}) on invoice {invoice.invoice_number}."
            ),
        )

    settings = db.query(OrganizationSettings).filter(
        OrganizationSettings.organization_id == tenant.id
    ).first()
    prefix = settings.credit_note_prefix if settings else "CRN"
    count = db.query(CreditNote).filter(CreditNote.tenant_id == tenant.id).count() + 1
    crn_number = f"{prefix}-{datetime.now(timezone.utc).year}-{count:05d}"

    credit_note = CreditNote(
        tenant_id=tenant.id,
        created_by=current_user.id,
        credit_note_number=crn_number,
        original_invoice_id=invoice.id,
        original_invoice_number=invoice.invoice_number,
        reason=data.reason,
        buyer_name=invoice.buyer_name,
        buyer_ntn=invoice.buyer_ntn,
        taxable_amount=data.taxable_amount,
        tax_amount=data.tax_amount,
        grand_total=data.grand_total,
        status=NoteStatus.READY.value,
        fbr_status="NOT_SUBMITTED",
        fbr_environment=settings.fbr_mode if settings else "DEMO",
        fbr_is_simulated=bool(settings and settings.fbr_mode in ("DEMO", "MOCK")),
    )
    db.add(credit_note)
    db.commit()
    db.refresh(credit_note)

    AuditService.log(
        db=db,
        tenant_id=tenant.id,
        action="CREATE_CREDIT_NOTE",
        entity="CreditNote",
        entity_id=credit_note.id,
        user_id=current_user.id,
        user_email=current_user.email,
        after_state={
            "credit_note_number": credit_note.credit_note_number,
            "original_invoice_number": credit_note.original_invoice_number,
            "grand_total": float(credit_note.grand_total),
        }
    )

    return credit_note


@router.post("/credit-notes/{id}/queue-submit", status_code=status.HTTP_202_ACCEPTED)
def queue_submit_credit_note(
    id: str,
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    note = db.query(CreditNote).filter(
        CreditNote.id == id,
        CreditNote.tenant_id == tenant.id
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="Credit note not found")

    if note.fbr_status == "VALID":
        return {"status": "ALREADY_ACCEPTED", "message": "Credit note already confirmed by FBR"}

    correlation_id = execution_context.correlation_id.get() or f"crn-corr-{uuid.uuid4().hex[:10]}"
    note.status = NoteStatus.QUEUED.value
    note.fbr_status = "PENDING"
    note.correlation_id = correlation_id
    db.commit()

    queue_service.enqueue_note_submission(
        note_type="CREDIT",
        note_id=note.id,
        tenant_id=tenant.id,
        correlation_id=correlation_id,
    )

    return {
        "status": "QUEUED",
        "note_id": note.id,
        "credit_note_number": note.credit_note_number,
        "correlation_id": correlation_id,
        "message": "Credit Note queued for asynchronous FBR fiscal registration.",
    }


@router.get("/credit-notes/{id}/pdf", response_model=DocumentDownloadResponse)
def get_credit_note_pdf(
    id: str,
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    note = db.query(CreditNote).filter(
        CreditNote.id == id,
        CreditNote.tenant_id == tenant.id
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="Credit note not found")

    invoice = db.query(Invoice).filter(Invoice.id == note.original_invoice_id).first()
    taxpayer = db.query(Taxpayer).filter(Taxpayer.tenant_id == tenant.id).first()

    # Generate PDF bytes
    pdf_bytes = pdf_generator.generate_note(
        note=note,
        note_type="CREDIT_NOTE",
        original_invoice=invoice,
        taxpayer=taxpayer,
    )

    file_name = f"{note.credit_note_number}.pdf"
    doc = document_service.store_document(
        db=db,
        tenant_id=tenant.id,
        entity_type="CREDIT_NOTE",
        entity_id=note.id,
        document_type=DocumentType.CREDIT_NOTE_PDF.value,
        file_name=file_name,
        mime_type="application/pdf",
        data=pdf_bytes,
        created_by=current_user.id,
        is_simulated=bool(note.fbr_is_simulated),
    )

    signed_url = document_service.get_signed_download_url(
        db=db,
        document_id=doc.id,
        tenant_id=tenant.id,
    )

    return DocumentDownloadResponse(
        document=DocumentResponse.model_validate(doc),
        download_url=signed_url.url,
        expires_at=signed_url.expires_at,
    )


@router.get("/debit-notes", response_model=List[DebitNoteResponse])
def list_debit_notes(
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    return db.query(DebitNote).filter(DebitNote.tenant_id == tenant.id).order_by(DebitNote.note_date.desc()).all()


@router.post("/debit-notes", response_model=DebitNoteResponse)
def create_debit_note(
    data: DebitNoteCreate,
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    invoice = db.query(Invoice).filter(
        Invoice.id == data.original_invoice_id,
        Invoice.tenant_id == tenant.id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Original invoice not found")

    if invoice.status in (InvoiceStatus.CANCELLED.value, InvoiceStatus.DRAFT.value):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot issue a Debit Note against an invoice in '{invoice.status}' status."
        )

    settings = db.query(OrganizationSettings).filter(
        OrganizationSettings.organization_id == tenant.id
    ).first()
    prefix = settings.debit_note_prefix if settings else "DBN"
    count = db.query(DebitNote).filter(DebitNote.tenant_id == tenant.id).count() + 1
    dbn_number = f"{prefix}-{datetime.now(timezone.utc).year}-{count:05d}"

    debit_note = DebitNote(
        tenant_id=tenant.id,
        created_by=current_user.id,
        debit_note_number=dbn_number,
        original_invoice_id=invoice.id,
        original_invoice_number=invoice.invoice_number,
        reason=data.reason,
        buyer_name=invoice.buyer_name,
        buyer_ntn=invoice.buyer_ntn,
        taxable_amount=data.taxable_amount,
        tax_amount=data.tax_amount,
        grand_total=data.grand_total,
        status=NoteStatus.READY.value,
        fbr_status="NOT_SUBMITTED",
        fbr_environment=settings.fbr_mode if settings else "DEMO",
        fbr_is_simulated=bool(settings and settings.fbr_mode in ("DEMO", "MOCK")),
    )
    db.add(debit_note)
    db.commit()
    db.refresh(debit_note)

    AuditService.log(
        db=db,
        tenant_id=tenant.id,
        action="CREATE_DEBIT_NOTE",
        entity="DebitNote",
        entity_id=debit_note.id,
        user_id=current_user.id,
        user_email=current_user.email,
        after_state={
            "debit_note_number": debit_note.debit_note_number,
            "original_invoice_number": debit_note.original_invoice_number,
            "grand_total": float(debit_note.grand_total),
        }
    )

    return debit_note


@router.post("/debit-notes/{id}/queue-submit", status_code=status.HTTP_202_ACCEPTED)
def queue_submit_debit_note(
    id: str,
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    note = db.query(DebitNote).filter(
        DebitNote.id == id,
        DebitNote.tenant_id == tenant.id
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="Debit note not found")

    if note.fbr_status == "VALID":
        return {"status": "ALREADY_ACCEPTED", "message": "Debit note already confirmed by FBR"}

    correlation_id = execution_context.correlation_id.get() or f"dbn-corr-{uuid.uuid4().hex[:10]}"
    note.status = NoteStatus.QUEUED.value
    note.fbr_status = "PENDING"
    note.correlation_id = correlation_id
    db.commit()

    queue_service.enqueue_note_submission(
        note_type="DEBIT",
        note_id=note.id,
        tenant_id=tenant.id,
        correlation_id=correlation_id,
    )

    return {
        "status": "QUEUED",
        "note_id": note.id,
        "debit_note_number": note.debit_note_number,
        "correlation_id": correlation_id,
        "message": "Debit Note queued for asynchronous FBR fiscal registration.",
    }


@router.get("/debit-notes/{id}/pdf", response_model=DocumentDownloadResponse)
def get_debit_note_pdf(
    id: str,
    tenant: Organization = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    note = db.query(DebitNote).filter(
        DebitNote.id == id,
        DebitNote.tenant_id == tenant.id
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="Debit note not found")

    invoice = db.query(Invoice).filter(Invoice.id == note.original_invoice_id).first()
    taxpayer = db.query(Taxpayer).filter(Taxpayer.tenant_id == tenant.id).first()

    pdf_bytes = pdf_generator.generate_note(
        note=note,
        note_type="DEBIT_NOTE",
        original_invoice=invoice,
        taxpayer=taxpayer,
    )

    file_name = f"{note.debit_note_number}.pdf"
    doc = document_service.store_document(
        db=db,
        tenant_id=tenant.id,
        entity_type="DEBIT_NOTE",
        entity_id=note.id,
        document_type=DocumentType.DEBIT_NOTE_PDF.value,
        file_name=file_name,
        mime_type="application/pdf",
        data=pdf_bytes,
        created_by=current_user.id,
        is_simulated=bool(note.fbr_is_simulated),
    )

    signed_url = document_service.get_signed_download_url(
        db=db,
        document_id=doc.id,
        tenant_id=tenant.id,
    )

    return DocumentDownloadResponse(
        document=DocumentResponse.model_validate(doc),
        download_url=signed_url.url,
        expires_at=signed_url.expires_at,
    )
