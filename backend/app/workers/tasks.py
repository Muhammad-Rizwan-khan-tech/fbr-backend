import json
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

from backend.app.core.database import SessionLocal
from backend.app.core.config import settings
from backend.app.core.context import execution_context
from backend.app.models.invoice import Invoice, InvoiceStatus, FBRSubmissionStatus
from backend.app.models.note import CreditNote, DebitNote, NoteStatus
from backend.app.models.tenant import OrganizationSettings
from backend.app.models.submission_job import InvoiceSubmissionJob, SubmissionJobStatus, TERMINAL_JOB_STATUSES
from backend.app.models.document import Document, DocumentType, BackgroundJob, BackgroundJobStatus
from backend.app.models.fbr import FBRSubmission, FBRSubmissionAttempt
from backend.app.models.base import now_utc
from backend.app.adapters.factory import FBRAdapterFactory
from backend.app.services.pdf_service import pdf_generator
from backend.app.services.document_service import document_service
from backend.app.services.notification_service import notification_service
from backend.app.services.audit_service import AuditService
from backend.app.monitoring.metrics import (
    record_fbr_submission,
    record_fbr_latency,
    record_pdf_generation,
    record_worker_job,
)
from backend.app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _build_fbr_payload(invoice: Invoice) -> dict:
    items_payload = []
    for itm in invoice.items:
        items_payload.append({
            "item_seq": itm.item_seq,
            "item_code": itm.item_code,
            "description": itm.description,
            "hs_code": itm.hs_code,
            "quantity": float(itm.quantity),
            "uom": itm.uom,
            "unit_price": float(itm.unit_price),
            "gross_amount": float(itm.gross_amount),
            "discount": float(itm.discount),
            "taxable_amount": float(itm.taxable_amount),
            "tax_rate": float(itm.tax_rate),
            "tax_amount": float(itm.tax_amount),
            "line_total": float(itm.line_total),
            "sale_type": itm.sale_type,
            "sro_reference": itm.sro_reference,
        })

    return {
        "invoice_number": invoice.invoice_number,
        "invoice_type": invoice.invoice_type,
        "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
        "seller_ntn": invoice.seller_ntn,
        "seller_strn": invoice.seller_strn,
        "seller_name": invoice.seller_name,
        "seller_branch_code": invoice.seller_branch_code,
        "seller_province": invoice.seller_province,
        "buyer_name": invoice.buyer_name,
        "buyer_ntn": invoice.buyer_ntn,
        "buyer_strn": invoice.buyer_strn,
        "buyer_cnic": invoice.buyer_cnic,
        "buyer_registration_type": invoice.buyer_registration_type,
        "buyer_province": invoice.buyer_province,
        "subtotal": float(invoice.subtotal),
        "total_discount": float(invoice.total_discount),
        "taxable_amount": float(invoice.taxable_amount),
        "total_tax": float(invoice.total_tax),
        "other_charges": float(invoice.other_charges),
        "grand_total": float(invoice.grand_total),
        "reference_number": invoice.reference_number,
        "notes": invoice.notes,
        "items": items_payload,
    }


@celery_app.task(name="backend.app.workers.tasks.submit_invoice_to_fbr_task")
def submit_invoice_to_fbr_task(job_id: str, correlation_id: str, tenant_id: str):
    """Processes an FBR invoice submission job asynchronously with idempotency,
    retries, exponential backoff, and dead-letter failure preservation.
    """
    execution_context.correlation_id.set(correlation_id)
    execution_context.tenant_id.set(tenant_id)
    execution_context.job_id.set(job_id)

    db = SessionLocal()
    start_time = time.time()
    try:
        job = (
            db.query(InvoiceSubmissionJob)
            .filter(
                InvoiceSubmissionJob.id == job_id,
                InvoiceSubmissionJob.tenant_id == tenant_id,
            )
            .first()
        )
        if not job:
            logger.error(f"Submission job {job_id} not found for tenant {tenant_id}")
            return {"error": "job_not_found"}

        if job.status in TERMINAL_JOB_STATUSES:
            logger.info(f"Submission job {job_id} is already in terminal state: {job.status}")
            inv = db.query(Invoice).filter(Invoice.id == job.invoice_id).first()
            return {
                "status": job.status,
                "message": "Already terminal",
                "fbr_invoice_number": inv.fbr_invoice_number if inv else None
            }

        # Transition to PROCESSING
        job.status = SubmissionJobStatus.PROCESSING.value
        job.started_at = now_utc()
        job.attempt_count += 1
        db.commit()

        invoice = (
            db.query(Invoice)
            .filter(Invoice.id == job.invoice_id, Invoice.tenant_id == tenant_id)
            .first()
        )
        if not invoice:
            job.status = SubmissionJobStatus.FAILED.value
            job.last_error_code = "INVOICE_NOT_FOUND"
            job.last_error_message = "Invoice linked to submission job does not exist."
            job.completed_at = now_utc()
            db.commit()
            record_worker_job("fbr_submission", "failed", time.time() - start_time)
            return {"error": "invoice_not_found"}

        if invoice.fbr_invoice_number and invoice.fbr_status == FBRSubmissionStatus.VALID.value:
            logger.info(f"Invoice {invoice.id} already verified with FBR ({invoice.fbr_invoice_number}). Skipping duplicate submission.")
            job.status = SubmissionJobStatus.ACCEPTED.value
            job.fbr_reference = invoice.fbr_invoice_number
            job.completed_at = now_utc()
            db.commit()
            return {"status": "ACCEPTED", "fbr_invoice_number": invoice.fbr_invoice_number}

        invoice.status = InvoiceStatus.SUBMITTING.value
        db.commit()

        # Resolve Adapter
        scenario = job.demo_scenario or "AUTO"
        adapter = FBRAdapterFactory.get_adapter(mode=job.environment, forced_scenario=scenario)
        payload = _build_fbr_payload(invoice)

        fbr_call_start = time.time()
        adapter_res = adapter.submit_invoice(payload)
        fbr_latency_ms = int((time.time() - fbr_call_start) * 1000)
        record_fbr_latency(job.environment, fbr_latency_ms / 1000.0)

        # Record submission attempt log
        attempt = FBRSubmissionAttempt(
            submission_id=None,
            attempt_number=job.attempt_count,
            request_data=json.dumps(payload),
            response_data=json.dumps(adapter_res.raw_response),
            http_status_code=200 if adapter_res.success else 400,
            status=adapter_res.status,
            error_message=adapter_res.error_message,
            latency_ms=fbr_latency_ms,
        )

        if adapter_res.status == "VALID" or (adapter_res.success and adapter_res.fbr_invoice_number):
            # SUCCESS (ACCEPTED)
            job.status = SubmissionJobStatus.ACCEPTED.value
            job.fbr_reference = adapter_res.fbr_reference
            job.completed_at = now_utc()
            job.last_error_code = None
            job.last_error_message = None

            invoice.status = InvoiceStatus.VALID.value
            invoice.fbr_status = FBRSubmissionStatus.VALID.value
            invoice.fbr_invoice_number = adapter_res.fbr_invoice_number
            invoice.fbr_qr_data = adapter_res.qr_code_data
            invoice.fbr_submission_date = now_utc()
            invoice.fbr_environment = job.environment
            invoice.fbr_provider = job.provider
            invoice.fbr_is_simulated = job.is_simulated
            invoice.fbr_error_code = None
            invoice.fbr_error_message = None

            # Persist FBR Submission record
            submission = FBRSubmission(
                tenant_id=tenant_id,
                created_by=job.created_by,
                invoice_id=invoice.id,
                job_id=job.id,
                environment=job.environment,
                provider=job.provider,
                is_simulated=job.is_simulated,
                adapter_name=adapter.__class__.__name__,
                status="VALID",
                fbr_invoice_number=adapter_res.fbr_invoice_number,
                fbr_reference=adapter_res.fbr_reference,
                qr_code_data=adapter_res.qr_code_data,
                request_payload=json.dumps(payload),
                response_payload=json.dumps(adapter_res.raw_response),
                submitted_at=now_utc(),
                responded_at=now_utc(),
            )
            db.add(submission)
            db.flush()

            attempt.submission_id = submission.id
            db.add(attempt)
            db.commit()

            record_fbr_submission(job.environment, "success")
            record_worker_job("fbr_submission", "success", time.time() - start_time)

            AuditService.log(
                db=db,
                tenant_id=tenant_id,
                action="FBR_SUBMIT_ASYNC_SUCCESS",
                entity="Invoice",
                entity_id=invoice.id,
                user_id=job.created_by,
                user_email="system@worker",
                after_state={
                    "status": "VALID",
                    "fbr_invoice_number": adapter_res.fbr_invoice_number,
                    "environment": job.environment,
                    "is_simulated": job.is_simulated,
                },
            )

            notification_service.notify_tenant_users(
                db=db,
                tenant_id=tenant_id,
                event_type="FBR_ACCEPTED",
                title=f"Invoice {invoice.invoice_number} Accepted by FBR",
                message=f"Invoice successfully registered with FBR. Official Ref: {adapter_res.fbr_invoice_number}",
                severity="SUCCESS",
                entity_type="INVOICE",
                entity_id=invoice.id,
                correlation_id=correlation_id,
            )

            # Auto-enqueue PDF generation for the accepted invoice
            from backend.app.services.queue_service import queue_service
            queue_service.enqueue_pdf_generation(
                invoice_id=invoice.id,
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                user_id=job.created_by,
            )

            # Fire Webhook: invoice.fbr_accepted
            from backend.app.services.webhook_service import webhook_service
            webhook_service.dispatch_event(
                db=db,
                tenant_id=tenant_id,
                event_type="invoice.fbr_accepted",
                payload_data={
                    "invoice_id": invoice.id,
                    "invoice_number": invoice.invoice_number,
                    "fbr_invoice_number": adapter_res.fbr_invoice_number,
                    "fbr_qr_data": adapter_res.qr_code_data,
                    "environment": job.environment,
                    "is_simulated": job.is_simulated,
                }
            )

            return {"status": "ACCEPTED", "fbr_invoice_number": adapter_res.fbr_invoice_number}

        elif adapter_res.is_retryable:
            # RETRYABLE TRANSIENT ERROR
            record_fbr_submission(job.environment, "retryable_error")
            submission = FBRSubmission(
                tenant_id=tenant_id,
                created_by=job.created_by,
                invoice_id=invoice.id,
                job_id=job.id,
                environment=job.environment,
                provider=job.provider,
                is_simulated=job.is_simulated,
                adapter_name=adapter.__class__.__name__,
                status="FAILED",
                error_code=adapter_res.error_code,
                error_message=adapter_res.error_message,
                is_retryable=True,
                request_payload=json.dumps(payload),
                response_payload=json.dumps(adapter_res.raw_response),
                submitted_at=now_utc(),
                responded_at=now_utc(),
            )
            db.add(submission)
            db.flush()
            attempt.submission_id = submission.id
            db.add(attempt)

            if job.attempt_count < job.max_attempts:
                # Schedule retry with exponential backoff
                delay = min(
                    settings.FBR_RETRY_INITIAL_DELAY_SECONDS * (settings.FBR_RETRY_BACKOFF_FACTOR ** (job.attempt_count - 1)),
                    settings.FBR_RETRY_MAX_DELAY_SECONDS,
                )
                job.status = SubmissionJobStatus.RETRYING.value
                job.next_retry_at = now_utc() + timedelta(seconds=delay)
                job.last_error_code = adapter_res.error_code or "RETRYABLE_ERROR"
                job.last_error_message = adapter_res.error_message

                invoice.status = InvoiceStatus.RETRYING.value
                invoice.fbr_status = FBRSubmissionStatus.PENDING.value
                invoice.fbr_error_code = adapter_res.error_code
                invoice.fbr_error_message = adapter_res.error_message
                db.commit()

                # Re-dispatch with delay
                from backend.app.services.queue_service import queue_service
                queue_service.enqueue_fbr_submission(
                    job_id=job.id,
                    tenant_id=tenant_id,
                    correlation_id=correlation_id,
                    countdown=delay,
                )
                record_worker_job("fbr_submission", "retrying", time.time() - start_time)
                return {"status": "RETRYING", "attempt": job.attempt_count, "next_retry_in_seconds": delay}
            else:
                # DEAD LETTER / RETRIES EXHAUSTED
                job.status = SubmissionJobStatus.FAILED.value
                job.completed_at = now_utc()
                job.last_error_code = adapter_res.error_code or "MAX_RETRIES_EXCEEDED"
                job.last_error_message = f"Exhausted {job.max_attempts} attempts. Last error: {adapter_res.error_message}"

                invoice.status = InvoiceStatus.FAILED.value
                invoice.fbr_status = FBRSubmissionStatus.FAILED.value
                invoice.fbr_error_code = job.last_error_code
                invoice.fbr_error_message = job.last_error_message
                db.commit()

                record_worker_job("fbr_submission", "failed", time.time() - start_time)

                notification_service.notify_tenant_users(
                    db=db,
                    tenant_id=tenant_id,
                    event_type="FBR_FAILED",
                    title=f"Invoice {invoice.invoice_number} FBR Submission Failed",
                    message=f"All {job.max_attempts} retry attempts exhausted. Error: {job.last_error_message}",
                    severity="ERROR",
                    entity_type="INVOICE",
                    entity_id=invoice.id,
                    correlation_id=correlation_id,
                )
                return {"status": "FAILED", "error": job.last_error_message}

        else:
            # PERMANENT ERROR / REJECTION (Do NOT retry)
            record_fbr_submission(job.environment, "rejected")
            job.status = SubmissionJobStatus.REJECTED.value
            job.completed_at = now_utc()
            job.last_error_code = adapter_res.error_code or "FBR_REJECTED"
            job.last_error_message = adapter_res.error_message

            invoice.status = InvoiceStatus.REJECTED.value
            invoice.fbr_status = FBRSubmissionStatus.INVALID.value
            invoice.fbr_error_code = adapter_res.error_code
            invoice.fbr_error_message = adapter_res.error_message

            submission = FBRSubmission(
                tenant_id=tenant_id,
                created_by=job.created_by,
                invoice_id=invoice.id,
                job_id=job.id,
                environment=job.environment,
                provider=job.provider,
                is_simulated=job.is_simulated,
                adapter_name=adapter.__class__.__name__,
                status="INVALID",
                error_code=adapter_res.error_code,
                error_message=adapter_res.error_message,
                is_retryable=False,
                request_payload=json.dumps(payload),
                response_payload=json.dumps(adapter_res.raw_response),
                submitted_at=now_utc(),
                responded_at=now_utc(),
            )
            db.add(submission)
            db.flush()
            attempt.submission_id = submission.id
            db.add(attempt)
            db.commit()

            record_worker_job("fbr_submission", "rejected", time.time() - start_time)

            notification_service.notify_tenant_users(
                db=db,
                tenant_id=tenant_id,
                event_type="FBR_REJECTED",
                title=f"Invoice {invoice.invoice_number} Rejected by FBR",
                message=f"Permanent validation rejection: {adapter_res.error_message}",
                severity="ERROR",
                entity_type="INVOICE",
                entity_id=invoice.id,
                correlation_id=correlation_id,
            )

            # Fire Webhook: invoice.fbr_rejected
            from backend.app.services.webhook_service import webhook_service
            webhook_service.dispatch_event(
                db=db,
                tenant_id=tenant_id,
                event_type="invoice.fbr_rejected",
                payload_data={
                    "invoice_id": invoice.id,
                    "invoice_number": invoice.invoice_number,
                    "error_code": adapter_res.error_code,
                    "error_message": adapter_res.error_message,
                    "environment": job.environment,
                }
            )

            return {"status": "REJECTED", "error": adapter_res.error_message}

    except Exception as exc:
        logger.exception(f"Unexpected worker exception processing FBR job {job_id}: {exc}")
        record_worker_job("fbr_submission", "error", time.time() - start_time)
        try:
            job = db.query(InvoiceSubmissionJob).filter(InvoiceSubmissionJob.id == job_id).first()
            if job and job.status not in TERMINAL_JOB_STATUSES:
                job.status = SubmissionJobStatus.FAILED.value
                job.last_error_code = "WORKER_EXCEPTION"
                job.last_error_message = str(exc)
                job.completed_at = now_utc()
                db.commit()
        except Exception:
            pass
        raise
    finally:
        db.close()


@celery_app.task(name="backend.app.workers.tasks.generate_invoice_pdf_task")
def generate_invoice_pdf_task(
    invoice_id: str, correlation_id: str, tenant_id: str, user_id: Optional[str] = None
):
    """Generates an official tax invoice PDF with QR code and stores it in object storage."""
    execution_context.correlation_id.set(correlation_id)
    execution_context.tenant_id.set(tenant_id)

    db = SessionLocal()
    start_time = time.time()
    try:
        invoice = (
            db.query(Invoice)
            .filter(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
            .first()
        )
        if not invoice:
            logger.error(f"Cannot generate PDF: invoice {invoice_id} not found for tenant {tenant_id}")
            return {"error": "invoice_not_found"}

        # Track background job
        bg_job = BackgroundJob(
            tenant_id=tenant_id,
            job_type="PDF_INVOICE",
            entity_type="INVOICE",
            entity_id=invoice_id,
            status=BackgroundJobStatus.PROCESSING.value,
            correlation_id=correlation_id,
            enqueued_at=now_utc(),
            started_at=now_utc(),
            created_by=user_id,
        )
        db.add(bg_job)
        db.commit()

        # Generate PDF bytes
        pdf_bytes = pdf_generator.generate(invoice)
        pdf_duration = time.time() - start_time
        record_pdf_generation(pdf_duration)

        # Store in document service
        file_name = f"{invoice.invoice_number}.pdf"
        doc = document_service.store_document(
            db=db,
            tenant_id=tenant_id,
            entity_type="INVOICE",
            entity_id=invoice.id,
            document_type=DocumentType.INVOICE_PDF.value,
            file_name=file_name,
            mime_type="application/pdf",
            data=pdf_bytes,
            created_by=user_id,
            is_simulated=bool(invoice.fbr_is_simulated),
        )

        bg_job.status = BackgroundJobStatus.COMPLETED.value
        bg_job.completed_at = now_utc()
        bg_job.result_document_id = doc.id
        db.commit()

        record_worker_job("pdf_generation", "success", pdf_duration)

        logger.info(
            f"Invoice PDF generated successfully for {invoice.invoice_number}, document {doc.id}"
        )
        return {"document_id": doc.id, "file_name": file_name, "size": len(pdf_bytes)}

    except Exception as exc:
        logger.exception(f"Failed to generate invoice PDF for {invoice_id}: {exc}")
        record_worker_job("pdf_generation", "error", time.time() - start_time)
        try:
            if 'bg_job' in locals() and bg_job:
                bg_job.status = BackgroundJobStatus.FAILED.value
                bg_job.last_error_code = "PDF_GEN_ERROR"
                bg_job.last_error_message = str(exc)
                bg_job.completed_at = now_utc()
                db.commit()
        except Exception:
            pass
        raise
    finally:
        db.close()


@celery_app.task(name="backend.app.workers.tasks.send_notification_task")
def send_notification_task(
    tenant_id: str,
    user_id: str,
    event_type: str,
    title: str,
    message: str,
    severity: str = "INFO",
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
):
    """Asynchronous notification dispatcher."""
    db = SessionLocal()
    try:
        return notification_service.create_notification(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            event_type=event_type,
            title=title,
            message=message,
            severity=severity,
            entity_type=entity_type,
            entity_id=entity_id,
            correlation_id=correlation_id,
        )
    finally:
        db.close()


@celery_app.task(name="backend.app.workers.tasks.reap_stale_jobs_task")
def reap_stale_jobs_task():
    """Periodically cleans up or retries stale in-flight jobs.
    Runs via Celery beat or periodic worker trigger.
    """
    db = SessionLocal()
    try:
        now = now_utc()
        stale_threshold = now - timedelta(minutes=15)
        stale_jobs = (
            db.query(InvoiceSubmissionJob)
            .filter(
                InvoiceSubmissionJob.status == SubmissionJobStatus.PROCESSING.value,
                InvoiceSubmissionJob.started_at < stale_threshold,
            )
            .all()
        )
        for job in stale_jobs:
            logger.warning(f"Reaping stale submission job {job.id} (started at {job.started_at})")
            job.status = SubmissionJobStatus.RETRYING.value
            job.last_error_code = "STALE_JOB_TIMEOUT"
            job.last_error_message = "Worker did not complete within the timeout window."
            job.next_retry_at = now
        db.commit()
    finally:
        db.close()


@celery_app.task(name="backend.app.workers.tasks.submit_note_to_fbr_task")
def submit_note_to_fbr_task(note_type: str, note_id: str, tenant_id: str, correlation_id: str):
    """Processes asynchronous FBR submission for Credit Notes and Debit Notes."""
    execution_context.correlation_id.set(correlation_id)
    execution_context.tenant_id.set(tenant_id)
    db = SessionLocal()
    start_time = time.time()
    try:
        is_credit = note_type.upper() == "CREDIT"
        note_model = CreditNote if is_credit else DebitNote
        note = db.query(note_model).filter(note_model.id == note_id, note_model.tenant_id == tenant_id).first()
        if not note:
            logger.error(f"{note_type} note {note_id} not found for tenant {tenant_id}")
            return {"error": "note_not_found"}

        if note.status == NoteStatus.VALID.value and note.fbr_status == "VALID":
            return {"status": "VALID", "message": "Already valid"}

        note.status = NoteStatus.PROCESSING.value
        db.commit()

        invoice = db.query(Invoice).filter(Invoice.id == note.original_invoice_id).first()
        org_settings = db.query(OrganizationSettings).filter(OrganizationSettings.organization_id == tenant_id).first()
        fbr_mode = org_settings.fbr_mode if org_settings else "DEMO"

        adapter = FBRAdapterFactory.get_adapter(mode=fbr_mode, tenant_settings=org_settings)

        payload = {
            "invoice_number": note.credit_note_number if is_credit else note.debit_note_number,
            "invoice_type": "CREDIT_NOTE" if is_credit else "DEBIT_NOTE",
            "original_invoice_number": note.original_invoice_number,
            "original_fbr_invoice_number": invoice.fbr_invoice_number if invoice else None,
            "reason": note.reason,
            "seller_ntn": invoice.seller_ntn if invoice else "1234567-8",
            "buyer_name": note.buyer_name,
            "buyer_ntn": note.buyer_ntn,
            "taxable_amount": float(note.taxable_amount),
            "total_tax": float(note.tax_amount),
            "grand_total": float(note.grand_total),
            "reference_number": note.original_invoice_number,
            "notes": note.reason,
            "items": [
                {
                    "item_seq": 1,
                    "item_code": "ADJ-NOTE",
                    "description": f"{note_type.title()} Note: {note.reason}",
                    "hs_code": "9900.00.00",
                    "quantity": 1.0,
                    "uom": "NOS",
                    "unit_price": float(note.taxable_amount),
                    "gross_amount": float(note.taxable_amount),
                    "discount": 0.0,
                    "taxable_amount": float(note.taxable_amount),
                    "tax_rate": 18.0,
                    "tax_amount": float(note.tax_amount),
                    "line_total": float(note.grand_total),
                    "sale_type": "SERVICES",
                }
            ],
        }

        res = adapter.submit_note(payload)

        if res.success and res.status == "VALID":
            note.status = NoteStatus.VALID.value
            note.fbr_status = "VALID"
            note.fbr_invoice_number = res.fbr_invoice_number
            note.fbr_reference = res.fbr_reference
            note.fbr_qr_data = res.qr_code_data
            note.fbr_submission_date = now_utc()
            note.fbr_environment = res.environment
            note.fbr_provider = res.provider
            note.fbr_is_simulated = res.is_simulated
            note.fbr_error_message = None
            note.correlation_id = correlation_id
            db.commit()

            notification_service.notify_tenant_users(
                db=db,
                tenant_id=tenant_id,
                event_type="FBR_NOTE_ACCEPTED",
                title=f"{note_type.title()} Note Registered with FBR",
                message=f"{note_type.title()} Note {payload['invoice_number']} successfully verified by FBR.",
                severity="INFO",
                entity_type=f"{note_type.upper()}_NOTE",
                entity_id=note.id,
                correlation_id=correlation_id,
            )
            return {"status": "VALID", "fbr_invoice_number": res.fbr_invoice_number}
        else:
            note.status = NoteStatus.FAILED.value
            note.fbr_status = "FAILED"
            note.fbr_error_message = res.error_message
            note.correlation_id = correlation_id
            db.commit()

            notification_service.notify_tenant_users(
                db=db,
                tenant_id=tenant_id,
                event_type="FBR_NOTE_FAILED",
                title=f"{note_type.title()} Note FBR Submission Failed",
                message=f"Submission failed: {res.error_message}",
                severity="ERROR",
                entity_type=f"{note_type.upper()}_NOTE",
                entity_id=note.id,
                correlation_id=correlation_id,
            )
            return {"status": "FAILED", "error": res.error_message}
    except Exception as exc:
        logger.exception(f"Exception submitting {note_type} note {note_id}: {exc}")
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="backend.app.workers.tasks.process_batch_fbr_submission_task")
def process_batch_fbr_submission_task(batch_job_id: str, tenant_id: str, correlation_id: str):
    """Processes bulk batch submissions of multiple invoices sequentially or concurrently with rate control."""
    execution_context.correlation_id.set(correlation_id)
    execution_context.tenant_id.set(tenant_id)
    db = SessionLocal()
    start_time = time.time()
    try:
        bg_job = db.query(BackgroundJob).filter(
            BackgroundJob.id == batch_job_id,
            BackgroundJob.tenant_id == tenant_id,
        ).first()
        if not bg_job:
            logger.error(f"Batch background job {batch_job_id} not found")
            return {"error": "batch_job_not_found"}

        bg_job.status = BackgroundJobStatus.PROCESSING.value
        bg_job.started_at = now_utc()
        db.commit()

        submission_jobs = db.query(InvoiceSubmissionJob).filter(
            InvoiceSubmissionJob.batch_job_id == batch_job_id,
            InvoiceSubmissionJob.tenant_id == tenant_id,
        ).all()

        total = len(submission_jobs)
        succeeded = 0
        failed = 0

        for s_job in submission_jobs:
            try:
                res = submit_invoice_to_fbr_task(
                    job_id=s_job.id,
                    correlation_id=f"{correlation_id}-{s_job.id[:6]}",
                    tenant_id=tenant_id,
                )
                if isinstance(res, dict) and res.get("status") in ("VALID", "ACCEPTED", "SUBMITTED"):
                    succeeded += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"Error processing batch item {s_job.id}: {e}")
                failed += 1

        db.refresh(bg_job)
        bg_job.status = BackgroundJobStatus.COMPLETED.value if failed == 0 else (
            BackgroundJobStatus.COMPLETED.value if succeeded > 0 else BackgroundJobStatus.FAILED.value
        )
        bg_job.completed_at = now_utc()
        bg_job.params = json.dumps({
            "total": total,
            "succeeded": succeeded,
            "failed": failed,
            "duration_seconds": round(time.time() - start_time, 2),
        })
        db.commit()

        notification_service.notify_tenant_users(
            db=db,
            tenant_id=tenant_id,
            event_type="BATCH_SUBMISSION_COMPLETED",
            title=f"Batch FBR Submission Completed ({succeeded}/{total} Success)",
            message=f"Processed batch of {total} invoices: {succeeded} accepted, {failed} rejected/failed.",
            severity="INFO" if failed == 0 else "WARNING",
            entity_type="BATCH_SUBMISSION",
            entity_id=batch_job_id,
            correlation_id=correlation_id,
        )

        # Fire Webhook: batch.completed
        from backend.app.services.webhook_service import webhook_service
        webhook_service.dispatch_event(
            db=db,
            tenant_id=tenant_id,
            event_type="batch.completed",
            payload_data={
                "batch_job_id": batch_job_id,
                "total": total,
                "succeeded": succeeded,
                "failed": failed,
            }
        )

        return {"batch_id": batch_job_id, "total": total, "succeeded": succeeded, "failed": failed}
    finally:
        db.close()


def dispatch_webhook_task(
    endpoint_id: str,
    tenant_id: str,
    event_type: str,
    payload_str: str,
    attempt: int = 1,
    max_attempts: int = 3,
) -> dict:
    """Delivers an outbound webhook HTTP POST request with HMAC-SHA256 signature and records delivery log."""
    db = SessionLocal()
    try:
        from backend.app.models.webhook import WebhookEndpoint, WebhookDelivery
        from backend.app.core.security import sign_webhook_payload
        import httpx

        ep = db.query(WebhookEndpoint).filter(
            WebhookEndpoint.id == endpoint_id,
            WebhookEndpoint.tenant_id == tenant_id,
            WebhookEndpoint.is_active == True
        ).first()

        if not ep:
            logger.warning(f"Webhook endpoint {endpoint_id} not found or inactive.")
            return {"status": "SKIPPED", "reason": "Endpoint not found or inactive"}

        timestamp = int(datetime.now(timezone.utc).timestamp())
        payload_bytes = payload_str.encode("utf-8")
        signature = sign_webhook_payload(ep.secret, payload_bytes, timestamp)

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "FBR-Invoice-Cloud-Webhooks/1.0",
            "X-FBR-Event": event_type,
            "X-FBR-Timestamp": str(timestamp),
            "X-FBR-Signature": signature,
        }

        start_time = time.time()
        response_status = None
        response_body = None
        error_msg = None
        success = False

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(ep.url, content=payload_bytes, headers=headers)
                response_status = resp.status_code
                response_body = resp.text[:1000]
                success = 200 <= resp.status_code < 300
        except Exception as exc:
            error_msg = str(exc)[:500]
            success = False

        duration_ms = int((time.time() - start_time) * 1000)
        delivery_status = "SUCCESS" if success else ("RETRYING" if attempt < max_attempts else "FAILED")

        delivery = WebhookDelivery(
            endpoint_id=ep.id,
            tenant_id=tenant_id,
            event_type=event_type,
            payload=payload_str,
            response_status=response_status,
            response_body=response_body,
            duration_ms=duration_ms,
            attempt=attempt,
            status=delivery_status,
            error_message=error_msg,
        )
        db.add(delivery)

        if success:
            ep.last_delivery_at = now_utc()
            ep.failure_count = 0
        else:
            ep.failure_count += 1
            if attempt < max_attempts:
                retry_delay = 60 * (2 ** (attempt - 1))
                from backend.app.services.queue_service import queue_service
                queue_service.enqueue_task(
                    "backend.app.workers.tasks.dispatch_webhook_task",
                    args=[endpoint_id, tenant_id, event_type, payload_str, attempt + 1, max_attempts],
                    queue_name="notifications",
                    countdown=retry_delay
                )

        db.commit()
        return {
            "endpoint_id": endpoint_id,
            "event": event_type,
            "status": delivery_status,
            "attempt": attempt,
            "duration_ms": duration_ms
        }
    finally:
        db.close()

