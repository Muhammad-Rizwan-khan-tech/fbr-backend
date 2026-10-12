from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class ActivationRedeemRequest(BaseModel):
    activation_key: str = Field(..., description="Permanent license activation secret (e.g. ACT-XXXX-XXXX-XXXX-XXXX)")
    device_fingerprint: str = Field(..., description="Unique hardware / machine fingerprint")
    device_name: Optional[str] = Field("Windows Terminal", description="Hostname or terminal friendly name")
    os_info: Optional[str] = Field("Windows", description="Client operating system")
    app_version: Optional[str] = Field("1.0.0", description="Desktop application build version")


class LicenseDetail(BaseModel):
    id: str
    license_number: str
    license_type: str
    status: str
    max_devices: int
    issued_at: datetime
    is_valid: bool


class OrgDetail(BaseModel):
    id: str
    name: str
    slug: str
    status: str


class ActivationRedeemResponse(BaseModel):
    success: bool
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    license: LicenseDetail
    organization: OrgDetail
    device_id: str


class TokenRefreshRequest(BaseModel):
    refresh_token: str
    device_fingerprint: str


class TokenRefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LicenseStatusResponse(BaseModel):
    license_number: str
    license_type: str
    status: str
    is_valid: bool
    device_id: Optional[str] = None
    device_status: Optional[str] = None
    organization_id: str
    organization_name: str
    fbr_mode: str
    message: str


class FBRConnectionPublicStatusResponse(BaseModel):
    is_configured: bool
    environment: str
    provider: str
    status: str
    fbr_pos_id: Optional[str] = None
    masked_api_key: Optional[str] = None
    last_tested_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_error: Optional[str] = None
