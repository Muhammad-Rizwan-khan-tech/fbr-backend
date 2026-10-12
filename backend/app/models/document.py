import enum

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint

from backend.app.core.database import Base
from backend.app.models.base import TenantMixin, generate_uuid, now_utc


class DocumentType(str, enum.Enum):
    INVOICE_PDF = "INVOICE_PDF"
    CREDIT_NOTE_PDF = "CREDIT_NOTE_PDF"
    DEBIT_NOTE_PDF = "DEBIT_NOTE_PDF"
    REPORT = "REPORT"
    EXPORT = "EXPORT"


class Document(Base):
    """Metadata for a file held in object storage. Binary content never lives in PostgreSQL."""
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), nullable=False, index=True)
    document_type = Column(String(30), nullable=False)
    entity_type = Column(String(30), nullable=False)   # Invoice | CreditNote | DebitNote | Report
    entity_id = Column(String(36), nullable=False)
    storage_provider = Column(String(20), nullable=False)
    storage_key = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    checksum = Column(String(64), nullable=False)       # sha256 hex
    version = Column(Integer, nullable=False, default=1)
    is_simulated = Column(Boolean, nullable=False, default=False)  # generated from DEMO/simulated FBR data
    created_by = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_utc)

    __table_args__ = (
        UniqueConstraint("tenant_id", "entity_type", "entity_id", "document_type", "version",
                         name="uq_documents_entity_version"),
        Index("ix_documents_tenant_entity", "tenant_id", "entity_type", "entity_id"),
    )


class BackgroundJobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    RETRYING = "RETRYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class BackgroundJob(Base, TenantMixin):
    """Generic tracked job (PDF generation, report/export generation)."""
    __tablename__ = "background_jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    job_type = Column(String(30), nullable=False, index=True)     # PDF_INVOICE | PDF_CREDIT_NOTE | PDF_DEBIT_NOTE | REPORT_EXPORT
    entity_type = Column(String(30), nullable=True)
    entity_id = Column(String(36), nullable=True)
    status = Column(String(20), nullable=False, default=BackgroundJobStatus.QUEUED.value, index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    enqueued_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    params = Column(Text, nullable=True)                           # JSON
    result_document_id = Column(String(36), nullable=True)
    last_error_code = Column(String(50), nullable=True)
    last_error_message = Column(Text, nullable=True)
    correlation_id = Column(String(50), nullable=False, index=True)

    __table_args__ = (
        Index("ix_background_jobs_tenant_entity", "tenant_id", "entity_type", "entity_id"),
    )
