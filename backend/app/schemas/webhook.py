from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, HttpUrl, ConfigDict


class WebhookEndpointCreate(BaseModel):
    url: str = Field(..., max_length=500, description="HTTPS endpoint destination URL")
    description: Optional[str] = Field(None, max_length=255)
    events: List[str] = Field(
        default=["invoice.created", "invoice.fbr_accepted", "invoice.fbr_rejected"],
        description="List of event names or ['*']"
    )


class WebhookEndpointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    url: str
    secret: str
    description: Optional[str] = None
    events: str
    is_active: bool
    failure_count: int
    last_delivery_at: Optional[datetime] = None
    created_at: datetime


class WebhookDeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    endpoint_id: str
    tenant_id: str
    event_type: str
    payload: str
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    duration_ms: int
    attempt: int
    status: str
    error_message: Optional[str] = None
    created_at: datetime
