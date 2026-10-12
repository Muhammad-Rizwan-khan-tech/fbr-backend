from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Friendly name (e.g. 'SAP Invoicing Integration')")
    environment: str = Field("TEST", description="TEST or LIVE")
    scopes: Optional[List[str]] = Field(default=["invoices:read", "invoices:write"], description="Allowed API scopes")
    rate_limit_per_minute: int = Field(60, ge=10, le=1000, description="Allowed requests per minute")
    expires_in_days: Optional[int] = Field(None, ge=1, le=365, description="Optional key expiration in days")


class ApiKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    name: str
    key_prefix: str
    environment: str
    scopes: str
    rate_limit_per_minute: int
    is_active: bool
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Returned ONLY upon initial creation. Contains plaintext key."""
    raw_api_key: str = Field(..., description="Copy this API key now. It will NEVER be shown again.")
