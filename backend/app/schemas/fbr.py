from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class FBRSubmissionAttemptResponse(BaseModel):
    id: str
    attempt_number: int
    http_status_code: Optional[int] = None
    status: str
    error_message: Optional[str] = None
    latency_ms: int
    created_at: datetime

    class Config:
        from_attributes = True


class FBRSubmissionResponse(BaseModel):
    id: str
    invoice_id: str
    environment: str
    adapter_name: str
    request_id: str
    correlation_id: Optional[str] = None
    status: str
    fbr_invoice_number: Optional[str] = None
    fbr_reference: Optional[str] = None
    qr_code_data: Optional[str] = None
    retry_count: int
    is_retryable: bool
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    gateway_diagnostics: Dict[str, Any] = {}
    submitted_at: datetime
    responded_at: Optional[datetime] = None
    attempts: List[FBRSubmissionAttemptResponse] = []

    class Config:
        from_attributes = True


class FBRStatusResponse(BaseModel):
    is_connected: bool
    connection_status: str = "NOT_CONFIGURED"  # NOT_CONFIGURED | CONFIGURED_NOT_VERIFIED | VERIFIED | AUTHENTICATION_FAILED | CONNECTION_UNAVAILABLE
    environment: str
    adapter: str
    last_tested_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_error: Optional[str] = None
    last_successful_submission: Optional[datetime] = None
    pending_queue_count: int = 0
    failed_submissions_count: int = 0
    total_valid_submissions: int = 0


class FBRTestConnectionResponse(BaseModel):
    status: str
    environment: str
    message: str
    success: bool = True
    latency_ms: int = 0
    details: Dict[str, Any] = {}
