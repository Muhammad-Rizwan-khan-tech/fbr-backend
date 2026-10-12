from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user, get_current_tenant
from backend.app.models.tenant import Organization
from backend.app.models.invoice import Invoice
from backend.app.models.note import CreditNote, DebitNote
from backend.app.models.fbr import FBRSubmission

router = APIRouter(prefix="/reports", tags=["Reports & Analytics"])


@router.get("/dashboard-kpis")
def get_dashboard_kpis(
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

    # Invoices
    today_invoices = db.query(Invoice).filter(
        Invoice.tenant_id == tenant.id,
        Invoice.invoice_date >= today_start
    ).count()

    month_invoices = db.query(Invoice).filter(
        Invoice.tenant_id == tenant.id,
        Invoice.invoice_date >= month_start
    ).count()

    valid_fbr_invoices = db.query(Invoice).filter(
        Invoice.tenant_id == tenant.id,
        Invoice.fbr_status == "VALID"
    ).count()

    pending_submissions = db.query(Invoice).filter(
        Invoice.tenant_id == tenant.id,
        Invoice.fbr_status == "PENDING"
    ).count()

    failed_submissions = db.query(Invoice).filter(
        Invoice.tenant_id == tenant.id,
        Invoice.fbr_status.in_(["FAILED", "INVALID"])
    ).count()

    # Sum totals
    financials = db.query(
        func.coalesce(func.sum(Invoice.taxable_amount), 0),
        func.coalesce(func.sum(Invoice.total_tax), 0),
        func.coalesce(func.sum(Invoice.grand_total), 0)
    ).filter(Invoice.tenant_id == tenant.id).first()

    credit_notes_count = db.query(CreditNote).filter(CreditNote.tenant_id == tenant.id).count()
    debit_notes_count = db.query(DebitNote).filter(DebitNote.tenant_id == tenant.id).count()

    return {
        "today_invoices_count": today_invoices,
        "monthly_invoices_count": month_invoices,
        "valid_fbr_count": valid_fbr_invoices,
        "pending_submissions_count": pending_submissions,
        "failed_submissions_count": failed_submissions,
        "total_taxable_amount": float(financials[0]),
        "total_tax": float(financials[1]),
        "total_grand_amount": float(financials[2]),
        "credit_notes_count": credit_notes_count,
        "debit_notes_count": debit_notes_count
    }


@router.get("/tax-summary")
def get_tax_summary(
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    # Group by tax status
    valid_tax = db.query(
        func.coalesce(func.sum(Invoice.taxable_amount), 0),
        func.coalesce(func.sum(Invoice.total_tax), 0)
    ).filter(Invoice.tenant_id == tenant.id, Invoice.fbr_status == "VALID").first()

    pending_tax = db.query(
        func.coalesce(func.sum(Invoice.taxable_amount), 0),
        func.coalesce(func.sum(Invoice.total_tax), 0)
    ).filter(Invoice.tenant_id == tenant.id, Invoice.fbr_status != "VALID").first()

    return {
        "verified_fbr_taxable": float(valid_tax[0]),
        "verified_fbr_tax": float(valid_tax[1]),
        "unverified_taxable": float(pending_tax[0]),
        "unverified_tax": float(pending_tax[1]),
        "currency": "PKR"
    }
