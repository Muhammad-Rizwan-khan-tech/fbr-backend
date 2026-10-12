import enum

from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text)

from backend.app.core.database import Base
from backend.app.models.base import TenantMixin, generate_uuid


class SubmissionJobStatus(str, enum.Enum):
    QUEUED = "QUEUED"          # persisted, waiting for a worker
    PROCESSING = "PROCESSING"  # claimed by a worker, adapter call in flight
    SUBMITTED = "SUBMITTED"    # accepted by the provider for async verification; status is polled
    ACCEPTED = "ACCEPTED"      # terminal: provider confirmed the invoice
    REJECTED = "REJECTED"      # terminal: provider rejected (permanent business error)
    RETRYING = "RETRYING"      # transient failure; next attempt scheduled at next_retry_at
    FAILED = "FAILED"          # terminal: retries exhausted or permanent technical failure (dead letter)


# Statuses during which another submission for the same invoice must NOT be created.
ACTIVE_JOB_STATUSES = ("QUEUED", "PROCESSING", "SUBMITTED", "RETRYING", "ACCEPTED")
IN_FLIGHT_JOB_STATUSES = ("QUEUED", "PROCESSING", "SUBMITTED", "RETRYING")
TERMINAL_JOB_STATUSES = ("ACCEPTED", "REJECTED", "FAILED")

_ACTIVE_SQL = "status IN ('QUEUED','PROCESSING','SUBMITTED','RETRYING','ACCEPTED')"


class InvoiceSubmissionJob(Base, TenantMixin):
    """Authoritative, persistent record of one FBR submission workflow for an invoice.

    Redis/Celery only carry a pointer (job_id); all state lives here.
    """
    __tablename__ = "invoice_submission_jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    invoice_id = Column(String(36), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_job_id = Column(String(36), nullable=True)  # set when created by a manual retry
    batch_job_id = Column(String(36), nullable=True, index=True)  # set when part of a bulk batch submission

    environment = Column(String(20), nullable=False)            # DEMO | SANDBOX | PRODUCTION
    provider = Column(String(40), nullable=False)               # MOCK | SANDBOX | LICENSED_INTEGRATOR | PRODUCTION
    is_simulated = Column(Boolean, nullable=False, default=False)
    demo_scenario = Column(String(30), nullable=True)           # DEMO only: forces a mock outcome

    status = Column(String(20), nullable=False, default=SubmissionJobStatus.QUEUED.value, index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=4)
    next_retry_at = Column(DateTime(timezone=True), nullable=True, index=True)
    enqueued_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    last_error_code = Column(String(50), nullable=True)
    last_error_message = Column(Text, nullable=True)
    fbr_reference = Column(String(100), nullable=True)

    correlation_id = Column(String(50), nullable=False, index=True)
    idempotency_key = Column(String(100), nullable=True)

    __table_args__ = (
        # API-level idempotency: same key, same tenant => same job.
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_submission_jobs_tenant_idem_key"),
        # DB-level duplicate protection: at most ONE live/accepted job per invoice.
        Index("uq_submission_jobs_one_active_per_invoice", "invoice_id", unique=True,
              sqlite_where=text(_ACTIVE_SQL), postgresql_where=text(_ACTIVE_SQL)),
        Index("ix_submission_jobs_tenant_status", "tenant_id", "status"),
    )
