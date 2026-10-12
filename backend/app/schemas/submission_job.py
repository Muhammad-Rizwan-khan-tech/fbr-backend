from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class InvoiceSubmissionJobResponse(BaseModel):
    id: str
    invoice_id: str
    parent_job_id: Optional[str] = None
    environment: str
    provider: str
    is_simulated: bool
    demo_scenario: Optional[str] = None
    status: str
    attempt_count: int
    max_attempts: int
    next_retry_at: Optional[datetime] = None
    enqueued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_error_code: Optional[str] = None
    last_error_message: Optional[str] = None
    fbr_reference: Optional[str] = None
    correlation_id: str
    idempotency_key: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
