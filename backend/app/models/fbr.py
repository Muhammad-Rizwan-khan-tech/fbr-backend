import json
from typing import Any, Dict
from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.base import generate_uuid, TenantMixin, TimestampMixin, now_utc


class FBRSubmission(Base, TenantMixin):
    __tablename__ = "fbr_submissions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    invoice_id = Column(String(36), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(String(36), ForeignKey("invoice_submission_jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Mode & Routing
    environment = Column(String(50), default="DEMO", nullable=False) # DEMO, SANDBOX, PRODUCTION
    adapter_name = Column(String(50), default="MockFBRAdapter", nullable=False)
    provider = Column(String(40), nullable=True)  # MOCK | SANDBOX | LICENSED_INTEGRATOR | PRODUCTION
    is_simulated = Column(Boolean, default=False, nullable=False)
    
    # Tracking & Idempotency
    request_id = Column(String(36), default=generate_uuid, nullable=False, index=True)
    correlation_id = Column(String(50), nullable=True, index=True)
    idempotency_key = Column(String(100), nullable=True, index=True)
    
    # State & Result
    status = Column(String(50), default="PENDING", nullable=False, index=True) # PENDING, VALID, INVALID, FAILED
    fbr_invoice_number = Column(String(100), nullable=True, index=True)
    fbr_reference = Column(String(100), nullable=True)
    qr_code_data = Column(Text, nullable=True)
    
    # Error & Retry Metadata
    retry_count = Column(Integer, default=0, nullable=False)
    is_retryable = Column(Boolean, default=False, nullable=False)
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    technical_details = Column(Text, nullable=True)
    
    # Payloads
    request_payload = Column(Text, nullable=True)
    response_payload = Column(Text, nullable=True)
    
    submitted_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    responded_at = Column(DateTime(timezone=True), nullable=True)

    invoice = relationship("Invoice", back_populates="submissions")
    attempts = relationship("FBRSubmissionAttempt", back_populates="submission", cascade="all, delete-orphan", order_by="FBRSubmissionAttempt.attempt_number")

    @property
    def gateway_diagnostics(self) -> Dict[str, Any]:
        """Expose only bounded safe gateway metadata, never full fiscal payloads."""
        try:
            data = json.loads(self.response_payload or "{}")
        except (TypeError, ValueError):
            return {}
        if not isinstance(data, dict):
            return {}
        safe_keys = ("http_status", "content_type", "response_kind",
                     "body_chars", "body_sha256_prefix", "array_items")
        return {key: data[key] for key in safe_keys if key in data}


class FBRSubmissionAttempt(Base, TimestampMixin):
    __tablename__ = "fbr_submission_attempts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    submission_id = Column(String(36), ForeignKey("fbr_submissions.id", ondelete="CASCADE"), nullable=False, index=True)
    
    attempt_number = Column(Integer, default=1, nullable=False)
    request_data = Column(Text, nullable=True)
    response_data = Column(Text, nullable=True)
    http_status_code = Column(Integer, nullable=True)
    status = Column(String(50), nullable=False)
    error_message = Column(Text, nullable=True)
    latency_ms = Column(Integer, default=0, nullable=False)

    submission = relationship("FBRSubmission", back_populates="attempts")
