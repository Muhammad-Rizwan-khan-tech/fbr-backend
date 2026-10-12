import json
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException

from backend.app.core.errors import ConflictError, NotFoundError, AppError
from backend.app.core.context import execution_context
from backend.app.core.config import settings as app_settings
from backend.app.models.tenant import OrganizationSettings
from backend.app.models.invoice import Invoice, InvoiceStatus, FBRSubmissionStatus
from backend.app.models.submission_job import (
    InvoiceSubmissionJob,
    SubmissionJobStatus,
    ACTIVE_JOB_STATUSES,
    IN_FLIGHT_JOB_STATUSES,
)
from backend.app.models.fbr import FBRSubmission, FBRSubmissionAttempt
from backend.app.adapters.factory import FBRAdapterFactory
from backend.app.services.audit_service import AuditService
from backend.app.services.queue_service import queue_service
from backend.app.models.base import now_utc


class FBRService:
    @staticmethod
    def _build_fbr_payload(invoice: Invoice, db: Optional[Session] = None) -> dict:
        items_payload = []
        for itm in invoice.items:
            rate_desc = f"{int(itm.tax_rate)}%" if float(itm.tax_rate).is_integer() else f"{float(itm.tax_rate)}%"
            sale_type_desc = "Goods at standard rate" if str(itm.sale_type).upper() == "STANDARD" else str(itm.sale_type)
            items_payload.append({
                "item_seq": itm.item_seq,
                "item_code": itm.item_code,
                "hs_code": itm.hs_code,
                "hsCode": itm.hs_code,
                "description": itm.description,
                "productDescription": itm.description,
                "rate": rate_desc,
                "tax_rate": float(itm.tax_rate),
                "uom": itm.uom,
                "uoM": itm.uom,
                "quantity": float(itm.quantity),
                "unit_price": float(itm.unit_price),
                "gross_amount": float(itm.gross_amount),
                "discount": float(itm.discount) if itm.discount and float(itm.discount) > 0 else 0.0,
                "taxable_amount": float(itm.taxable_amount),
                "valueSalesExcludingST": float(itm.taxable_amount),
                "tax_amount": float(itm.tax_amount),
                "salesTaxApplicable": float(itm.tax_amount),
                "line_total": float(itm.line_total),
                "totalValues": float(itm.line_total),
                "fixedNotifiedValueOrRetailPrice": 0.0,
                "salesTaxWithheldAtSource": 0.0,
                "sale_type": sale_type_desc,
                "saleType": sale_type_desc,
                "sro_reference": itm.sro_reference,
                "sroScheduleNo": itm.sro_reference if itm.sro_reference else None,
            })

        seller_address = ""
        session = db
        if not session:
            try:
                from sqlalchemy.orm import object_session
                session = object_session(invoice)
            except Exception:
                session = None

        if session and invoice.branch_id:
            try:
                from backend.app.models.branch import Branch
                branch = session.query(Branch).filter(Branch.id == invoice.branch_id).first()
                if branch and branch.address:
                    seller_address = branch.address
            except Exception:
                pass

        if not seller_address and session and invoice.tenant_id:
            try:
                from backend.app.models.taxpayer import Taxpayer
                taxpayer = session.query(Taxpayer).filter(Taxpayer.tenant_id == invoice.tenant_id).first()
                if taxpayer and taxpayer.address:
                    seller_address = taxpayer.address
            except Exception:
                pass

        if not seller_address:
            seller_address = f"{invoice.seller_province}, Pakistan" if invoice.seller_province else "Pakistan"

        is_debit = "DEBIT" in str(invoice.invoice_type).upper()
        official_inv_type = "Debit Note" if is_debit else "Sale Invoice"
        reg_type = "Registered" if str(invoice.buyer_registration_type).upper() in ("REGISTERED", "REGISTERED_BUSINESS") else "Unregistered"
        buyer_ntn_cnic = invoice.buyer_ntn or invoice.buyer_cnic or ("1111111" if reg_type == "Unregistered" else "")
        date_str = invoice.invoice_date.strftime("%Y-%m-%d") if invoice.invoice_date else datetime.now(timezone.utc).strftime("%Y-%m-%d")

        return {
            "invoice_number": invoice.invoice_number,
            "invoice_type": official_inv_type,
            "invoiceType": official_inv_type,
            "invoice_date": date_str,
            "invoiceDate": date_str,
            "seller_ntn": invoice.seller_ntn,
            "sellerNTNCNIC": invoice.seller_ntn,
            "seller_strn": invoice.seller_strn,
            "seller_name": invoice.seller_name,
            "sellerBusinessName": invoice.seller_name,
            "seller_branch_code": invoice.seller_branch_code,
            "seller_province": invoice.seller_province,
            "sellerProvince": invoice.seller_province,
            "seller_address": seller_address,
            "sellerAddress": seller_address,
            "buyer_name": invoice.buyer_name,
            "buyerBusinessName": invoice.buyer_name,
            "buyer_ntn": invoice.buyer_ntn,
            "buyer_cnic": invoice.buyer_cnic,
            "buyerNTNCNIC": buyer_ntn_cnic,
            "buyer_strn": invoice.buyer_strn,
            "buyer_registration_type": reg_type,
            "buyerRegistrationType": reg_type,
            "buyer_address": invoice.buyer_address,
            "buyerAddress": invoice.buyer_address,
            "buyer_province": invoice.buyer_province,
            "buyerProvince": invoice.buyer_province,
            "subtotal": float(invoice.subtotal),
            "total_discount": float(invoice.total_discount),
            "taxable_amount": float(invoice.taxable_amount),
            "total_tax": float(invoice.total_tax),
            "other_charges": float(invoice.other_charges),
            "grand_total": float(invoice.grand_total),
            "reference_number": invoice.reference_number,
            "invoiceRefNo": invoice.reference_number if is_debit else None,
            "notes": invoice.notes,
            "items": items_payload,
        }

    @classmethod
    def submit_invoice(
        cls,
        db: Session,
        invoice: Invoice,
        user_id: str,
        user_email: str,
        forced_scenario: str = "AUTO"
    ) -> FBRSubmission:
        if invoice.fbr_status == FBRSubmissionStatus.VALID.value:
            raise HTTPException(status_code=400, detail="Invoice has already been successfully submitted and verified with FBR")

        invoice.status = InvoiceStatus.SUBMITTING.value
        db.commit()

        settings = db.query(OrganizationSettings).filter(
            OrganizationSettings.organization_id == invoice.tenant_id
        ).first()
        fbr_mode = settings.fbr_mode if settings else "DEMO"

        adapter = FBRAdapterFactory.get_adapter(mode=fbr_mode, forced_scenario=forced_scenario)
        payload = cls._build_fbr_payload(invoice, db=db)
        
        start_time = time.time()
        adapter_res = adapter.submit_invoice(payload)
        latency = int((time.time() - start_time) * 1000)

        # Create or update submission record
        submission = FBRSubmission(
            tenant_id=invoice.tenant_id,
            created_by=user_id,
            invoice_id=invoice.id,
            environment=fbr_mode,
            adapter_name=adapter.__class__.__name__,
            status=adapter_res.status,
            fbr_invoice_number=adapter_res.fbr_invoice_number,
            fbr_reference=adapter_res.fbr_reference,
            qr_code_data=adapter_res.qr_code_data,
            error_code=adapter_res.error_code,
            error_message=adapter_res.error_message,
            is_retryable=adapter_res.is_retryable,
            request_payload=json.dumps(payload),
            response_payload=json.dumps(adapter_res.raw_response),
            submitted_at=now_utc(),
            responded_at=now_utc()
        )
        db.add(submission)
        db.flush()

        # Add attempt log
        attempt = FBRSubmissionAttempt(
            submission_id=submission.id,
            attempt_number=1,
            request_data=json.dumps(payload),
            response_data=json.dumps(adapter_res.raw_response),
            http_status_code=200 if adapter_res.success else 400,
            status=adapter_res.status,
            error_message=adapter_res.error_message,
            latency_ms=latency
        )
        db.add(attempt)

        # Sync invoice state
        if adapter_res.status == "VALID":
            invoice.status = InvoiceStatus.VALID.value
            invoice.fbr_status = FBRSubmissionStatus.VALID.value
            invoice.fbr_invoice_number = adapter_res.fbr_invoice_number
            invoice.fbr_qr_data = adapter_res.qr_code_data
            invoice.fbr_submission_date = now_utc()
            invoice.fbr_error_code = None
            invoice.fbr_error_message = None
        elif adapter_res.status == "PENDING":
            invoice.status = InvoiceStatus.SUBMITTED.value
            invoice.fbr_status = FBRSubmissionStatus.PENDING.value
            invoice.fbr_error_code = adapter_res.error_code
            invoice.fbr_error_message = adapter_res.error_message
        else:
            invoice.status = InvoiceStatus.FAILED.value
            invoice.fbr_status = FBRSubmissionStatus.FAILED.value
            invoice.fbr_error_code = adapter_res.error_code
            invoice.fbr_error_message = adapter_res.error_message

        db.commit()
        db.refresh(submission)

        AuditService.log(
            db=db,
            tenant_id=invoice.tenant_id,
            action="FBR_SUBMIT",
            entity="FBRSubmission",
            entity_id=submission.id,
            user_id=user_id,
            user_email=user_email,
            after_state={
                "status": submission.status,
                "fbr_invoice_number": submission.fbr_invoice_number,
                "error_code": submission.error_code
            }
        )

        return submission

    @classmethod
    def retry_submission(
        cls,
        db: Session,
        submission_id: str,
        user_id: str,
        user_email: str
    ) -> FBRSubmission:
        submission = db.query(FBRSubmission).filter(FBRSubmission.id == submission_id).first()
        if not submission:
            raise HTTPException(status_code=404, detail="Submission record not found")

        invoice = db.query(Invoice).filter(Invoice.id == submission.invoice_id).first()
        if not invoice:
            raise HTTPException(status_code=404, detail="Associated invoice not found")

        # For retry, we clear any transient failure scenario and perform standard submission
        adapter = FBRAdapterFactory.get_adapter(mode=submission.environment, forced_scenario="VALID")
        payload = cls._build_fbr_payload(invoice, db=db)

        start_time = time.time()
        adapter_res = adapter.submit_invoice(payload)
        latency = int((time.time() - start_time) * 1000)

        submission.retry_count += 1
        submission.status = adapter_res.status
        submission.fbr_invoice_number = adapter_res.fbr_invoice_number or submission.fbr_invoice_number
        submission.fbr_reference = adapter_res.fbr_reference or submission.fbr_reference
        submission.qr_code_data = adapter_res.qr_code_data or submission.qr_code_data
        submission.error_code = adapter_res.error_code
        submission.error_message = adapter_res.error_message
        submission.is_retryable = adapter_res.is_retryable
        submission.response_payload = json.dumps(adapter_res.raw_response)
        submission.responded_at = now_utc()

        attempt = FBRSubmissionAttempt(
            submission_id=submission.id,
            attempt_number=submission.retry_count + 1,
            request_data=json.dumps(payload),
            response_data=json.dumps(adapter_res.raw_response),
            http_status_code=200 if adapter_res.success else 400,
            status=adapter_res.status,
            error_message=adapter_res.error_message,
            latency_ms=latency
        )
        db.add(attempt)

        if adapter_res.status == "VALID":
            invoice.status = InvoiceStatus.VALID.value
            invoice.fbr_status = FBRSubmissionStatus.VALID.value
            invoice.fbr_invoice_number = adapter_res.fbr_invoice_number
            invoice.fbr_qr_data = adapter_res.qr_code_data
            invoice.fbr_submission_date = now_utc()
            invoice.fbr_error_code = None
            invoice.fbr_error_message = None
        else:
            invoice.status = InvoiceStatus.FAILED.value
            invoice.fbr_status = FBRSubmissionStatus.FAILED.value
            invoice.fbr_error_code = adapter_res.error_code
            invoice.fbr_error_message = adapter_res.error_message

        db.commit()
        db.refresh(submission)

        AuditService.log(
            db=db,
            tenant_id=invoice.tenant_id,
            action="FBR_RETRY",
            entity="FBRSubmission",
            entity_id=submission.id,
            user_id=user_id,
            user_email=user_email,
            after_state={"status": submission.status, "attempt": submission.retry_count + 1}
        )

        return submission

    @classmethod
    def queue_invoice_submission(
        cls,
        db: Session,
        invoice: Invoice,
        user_id: str,
        user_email: str,
        idempotency_key: Optional[str] = None,
        forced_scenario: str = "AUTO",
        batch_job_id: Optional[str] = None,
        auto_dispatch: bool = True,
    ) -> InvoiceSubmissionJob:
        """Asynchronously queues an invoice for FBR submission.
        
        Strictly enforces:
        1. API-level idempotency via Idempotency-Key
        2. Database-level state guards (prevents duplicate submission if already VALID or in-flight)
        3. Clear provenance tracking (DEMO/MOCK vs PRODUCTION)
        """
        # 1. Check if invoice is already accepted
        if invoice.fbr_status == FBRSubmissionStatus.VALID.value or invoice.status == InvoiceStatus.VALID.value:
            existing_accepted = (
                db.query(InvoiceSubmissionJob)
                .filter(
                    InvoiceSubmissionJob.invoice_id == invoice.id,
                    InvoiceSubmissionJob.status == SubmissionJobStatus.ACCEPTED.value,
                )
                .first()
            )
            if existing_accepted:
                return existing_accepted
            raise ConflictError("Invoice has already been registered and verified with FBR.")

        # 2. Check Idempotency Key
        if idempotency_key:
            existing_by_key = (
                db.query(InvoiceSubmissionJob)
                .filter(
                    InvoiceSubmissionJob.tenant_id == invoice.tenant_id,
                    InvoiceSubmissionJob.idempotency_key == idempotency_key,
                )
                .first()
            )
            if existing_by_key:
                return existing_by_key

        # 3. Check for existing active submission job for this invoice
        active_job = (
            db.query(InvoiceSubmissionJob)
            .filter(
                InvoiceSubmissionJob.invoice_id == invoice.id,
                InvoiceSubmissionJob.status.in_(ACTIVE_JOB_STATUSES),
            )
            .first()
        )
        if active_job:
            if active_job.status in IN_FLIGHT_JOB_STATUSES:
                return active_job
            elif active_job.status == SubmissionJobStatus.ACCEPTED.value:
                return active_job

        # 4. Resolve environment and provenance
        org_settings = db.query(OrganizationSettings).filter(
            OrganizationSettings.organization_id == invoice.tenant_id
        ).first()
        fbr_mode = org_settings.fbr_mode if org_settings else "DEMO"
        is_simulated = bool(fbr_mode.upper() in ("DEMO", "MOCK"))
        provider = "MOCK" if is_simulated else (fbr_mode.upper())

        correlation_id = execution_context.correlation_id.get() or f"fbr-corr-{uuid.uuid4().hex[:12]}"

        # 5. Create authoritative submission job
        job = InvoiceSubmissionJob(
            tenant_id=invoice.tenant_id,
            invoice_id=invoice.id,
            batch_job_id=batch_job_id,
            environment=fbr_mode,
            provider=provider,
            is_simulated=is_simulated,
            demo_scenario=forced_scenario,
            status=SubmissionJobStatus.QUEUED.value,
            attempt_count=0,
            max_attempts=app_settings.FBR_RETRY_MAX_ATTEMPTS,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            enqueued_at=now_utc(),
            created_by=user_id,
        )
        db.add(job)

        # Update invoice state
        invoice.status = InvoiceStatus.QUEUED.value
        invoice.fbr_environment = fbr_mode
        invoice.fbr_provider = provider
        invoice.fbr_is_simulated = is_simulated
        invoice.correlation_id = correlation_id
        db.commit()
        db.refresh(job)

        # 6. Dispatch to background queue if auto_dispatch is enabled
        if auto_dispatch:
            queue_service.enqueue_fbr_submission(
                job_id=job.id,
                tenant_id=invoice.tenant_id,
                correlation_id=correlation_id,
            )

        AuditService.log(
            db=db,
            tenant_id=invoice.tenant_id,
            action="FBR_SUBMIT_QUEUED",
            entity="InvoiceSubmissionJob",
            entity_id=job.id,
            user_id=user_id,
            user_email=user_email,
            after_state={
                "status": "QUEUED",
                "invoice_id": invoice.id,
                "environment": fbr_mode,
                "provider": provider,
                "is_simulated": is_simulated,
            },
        )

        return job

    @classmethod
    def get_submission_job(cls, db: Session, job_id: str, tenant_id: str) -> InvoiceSubmissionJob:
        job = (
            db.query(InvoiceSubmissionJob)
            .filter(
                InvoiceSubmissionJob.id == job_id,
                InvoiceSubmissionJob.tenant_id == tenant_id,
            )
            .first()
        )
        if not job:
            raise NotFoundError(f"Submission job {job_id} not found.")
        return job

    @classmethod
    def list_submission_jobs_for_invoice(
        cls, db: Session, invoice_id: str, tenant_id: str
    ) -> List[InvoiceSubmissionJob]:
        return (
            db.query(InvoiceSubmissionJob)
            .filter(
                InvoiceSubmissionJob.invoice_id == invoice_id,
                InvoiceSubmissionJob.tenant_id == tenant_id,
            )
            .order_by(desc(InvoiceSubmissionJob.created_at))
            .all()
        )

