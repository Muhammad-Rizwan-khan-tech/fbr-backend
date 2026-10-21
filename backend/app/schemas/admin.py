from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr


class AdminCreateOrgRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Legal business / company name")
    ntn: str = Field(..., min_length=7, max_length=15, description="National Tax Number")
    strn: Optional[str] = Field(None, max_length=20, description="Sales Tax Registration Number")
    province: str = Field(..., min_length=2, max_length=50, description="e.g. Sindh, Punjab, ICT")
    city: Optional[str] = Field("Karachi", max_length=100, description="City name")
    address: str = Field(..., min_length=5, max_length=500, description="Principal business address")
    admin_email: EmailStr = Field(..., description="Default Organization Admin email")
    admin_name: str = Field("Organization Admin", description="Default Admin full name")
    admin_password: Optional[str] = Field(None, description="Optional custom initial password")
    max_devices: int = Field(5, ge=1, le=50, description="Maximum allowed active desktop devices")
    
    # Optional initial FBR configuration
    fbr_environment: Optional[str] = Field("DEMO", description="DEMO | SANDBOX | PRODUCTION")
    fbr_provider: Optional[str] = Field("MOCK", description="MOCK | SANDBOX | LICENSED_INTEGRATOR | PRODUCTION")
    fbr_pos_id: Optional[str] = None
    fbr_api_key: Optional[str] = None
    fbr_client_id: Optional[str] = None
    fbr_client_secret: Optional[str] = None
    fbr_auth_token: Optional[str] = None
    business_activity: Optional[str] = Field("MANUFACTURER", description="MANUFACTURER | DISTRIBUTOR | WHOLESALER | EXPORTER | RETAILER | SERVICE_PROVIDER | OTHER")
    business_sector: Optional[str] = None


class AdminUpdateOrgRequest(BaseModel):
    name: Optional[str] = None
    ntn: Optional[str] = None
    strn: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    max_devices: Optional[int] = None


class AdminSetStatusRequest(BaseModel):
    status: str = Field(..., description="ACTIVE | SUSPENDED")
    reason: Optional[str] = None


class AdminSetFBRCredentialsRequest(BaseModel):
    environment: str = Field("DEMO", description="DEMO | SANDBOX | PRODUCTION")
    provider: str = Field("MOCK", description="MOCK | SANDBOX | LICENSED_INTEGRATOR | PRODUCTION")
    fbr_pos_id: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    auth_token: Optional[str] = None
    cert_passphrase: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    production_ready: Optional[bool] = False
    sandbox_tested: Optional[bool] = False


class AdminReissueKeyRequest(BaseModel):
    reason: Optional[str] = Field("Admin requested key re-issuance", description="Audit rationale")


class AdminDeviceActionRequest(BaseModel):
    reason: Optional[str] = Field(None, description="Reason for device revocation or status change")


class AdminReissueKeyResponse(BaseModel):
    success: bool
    license_id: str
    license_number: str
    one_time_activation_secret: str
    expires_at: Optional[datetime] = None
    message: str = "Activation key generated. Reveal to customer once and store securely."


class AdminDeviceResponse(BaseModel):
    id: str
    organization_id: str
    license_id: str
    device_fingerprint: str
    device_name: str
    os_info: str
    app_version: str
    ip_address: Optional[str]
    status: str
    activated_at: datetime
    last_seen_at: datetime
    revoked_at: Optional[datetime] = None
    revocation_reason: Optional[str] = None


class AdminOrgSummary(BaseModel):
    id: str
    name: str
    slug: str
    status: str
    ntn: Optional[str] = None
    strn: Optional[str] = None
    province: Optional[str] = None
    license_number: Optional[str] = None
    license_status: Optional[str] = None
    active_devices_count: int
    max_devices: int
    fbr_status: str
    fbr_provider: str
    invoices_count: int
    created_at: datetime


class AdminOrgDetailResponse(BaseModel):
    organization: Dict[str, Any]
    taxpayer: Optional[Dict[str, Any]]
    license: Optional[Dict[str, Any]]
    pending_activation_key: Optional[Dict[str, Any]]
    fbr_credentials: Optional[Dict[str, Any]]
    devices: List[AdminDeviceResponse]
    stats: Dict[str, Any]


class AdminAuditLogItem(BaseModel):
    id: str
    admin_identity: str
    action: str
    target_type: str
    target_id: str
    details: Optional[str]
    ip_address: Optional[str]
    created_at: datetime


class AdminStatsResponse(BaseModel):
    total_organizations: int
    active_organizations: int
    suspended_organizations: int
    total_licenses: int
    active_licenses: int
    revoked_licenses: int
    total_devices: int
    active_devices: int
    total_invoices: int
    submitted_invoices: int
    fbr_healthy_count: int
    fbr_failed_count: int


# --- Simplified 3-Field Admin Client Management Schemas ---

class AdminCreateClientRequest(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=255, description="Client legal / company name")
    username: str = Field(..., min_length=3, max_length=50, description="Client unique username for desktop terminal")
    fbr_api_token: str = Field(..., min_length=1, description="PRAL-issued FBR API authorization token")
    # Optional for backwards-compatible 3-field client creation. Missing details
    # remain *unconfigured*, never invented using a placeholder NTN or address.
    ntn: Optional[str] = Field(None, max_length=20)
    strn: Optional[str] = Field(None, max_length=30)
    province: Optional[str] = Field(None, max_length=100)
    city: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=500)
    fbr_pos_id: Optional[str] = Field(None, max_length=50)
    business_activity: Optional[str] = Field(None, max_length=100)


class AdminUpdateClientRequest(BaseModel):
    company_name: Optional[str] = Field(None, min_length=2, max_length=255)
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    ntn: Optional[str] = Field(None, max_length=20)
    strn: Optional[str] = Field(None, max_length=30)
    province: Optional[str] = Field(None, max_length=100)
    city: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=500)
    fbr_pos_id: Optional[str] = Field(None, max_length=50)
    business_activity: Optional[str] = Field(None, max_length=100)


class AdminUpdateClientFBRTokenRequest(BaseModel):
    fbr_api_token: str = Field(..., min_length=1, description="New PRAL-issued FBR API authorization token")
    environment: Optional[str] = Field(None, pattern="^(SANDBOX|PRODUCTION)$", description="Required for changing operating environment; unchanged when omitted")


class AdminClientListItem(BaseModel):
    id: str
    company_name: str
    username: str
    fbr_status: str
    license_status: str
    activation_status: str
    license_id: Optional[str] = None
    license_number: Optional[str] = None
    created_at: str


class AdminCreateClientResponse(BaseModel):
    success: bool = True
    organization_id: str
    company_name: str
    username: str
    activation_key: str
    license_id: str
    license_number: str
    license_status: str = "ACTIVE"
    activation_status: str = "Not Activated"
    fbr_status: str = "Configured — Not Verified"
    message: str = "Client created successfully. Reveal the activation key to the customer once."

