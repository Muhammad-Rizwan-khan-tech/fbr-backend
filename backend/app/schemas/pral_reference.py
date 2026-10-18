"""PRAL Digital Invoicing v1.12 Reference API wire schemas, normalized DTOs,
and provenance envelopes (Section 5, pages 22-34).
"""
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar
from pydantic import BaseModel, ConfigDict, Field


class ProviderMode(str, Enum):
    FIXTURE = "fixture"  # DEMO_FIXTURE
    CACHED_OFFICIAL = "cached_official"  # OFFICIAL_IMPORT / CACHED_OFFICIAL
    AUTHORIZED_LIVE = "authorized_live"  # PRAL_LIVE


class DataSourceTag(str, Enum):
    DEMO_FIXTURE = "DEMO_FIXTURE"
    OFFICIAL_IMPORT = "OFFICIAL_IMPORT"
    CACHED_OFFICIAL = "CACHED_OFFICIAL"
    PRAL_LIVE = "PRAL_LIVE"


class StatlTransportStrategy(str, Enum):
    """Transport strategies for Sections 5.11 (statl) and 5.12 (Get_Reg_Type)
    because the PRAL v1.12 PDF shows GET method with sample JSON request bodies.
    """
    QUERY_PARAMS = "query_params"
    JSON_BODY_GET = "json_body_get"
    POST_FALLBACK = "post_fallback"


# ---------------------------------------------------------------------------
# 1. Wire-Exact PRAL v1.12 Response Models (Section 5.1 - 5.12)
# ---------------------------------------------------------------------------

class WireProvinceItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    stateProvinceCode: int
    stateProvinceDesc: str


class WireDocTypeItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    docTypeId: int
    docDescription: str


class WireItemDescCodeItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    hS_CODE: str
    description: str


class WireSroItemCodeItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    srO_ITEM_ID: int
    srO_ITEM_DESC: str


class WireTransTypeCodeItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    transactioN_TYPE_ID: int
    transactioN_DESC: str


class WireUomItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    uoM_ID: int
    description: str


class WireSroScheduleItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    srO_ID: int
    srO_DESC: str


class WireSaleTypeToRateItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    ratE_ID: int
    ratE_DESC: str
    ratE_VALUE: float


class WireHsUomItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    uoM_ID: int
    description: str


class WireSroItemByScheduleItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    srO_ITEM_ID: int
    srO_ITEM_DESC: str


class WireStatlResponse(BaseModel):
    """Section 5.11 STATL response: {"status code": "01", "status": "Active"}"""
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    status_code: str = Field(alias="status code", default="")
    status: str = Field(default="")


class WireGetRegTypeResponse(BaseModel):
    """Section 5.12 Get_Reg_Type response:
    {"statuscode": "00", "REGISTRATION_NO": "0788762", "REGISTRATION_TYPE": "Registered"}
    """
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    statuscode: str = Field(default="")
    REGISTRATION_NO: str = Field(default="")
    REGISTRATION_TYPE: str = Field(default="")


# ---------------------------------------------------------------------------
# 2. Normalized + Wire-Compatible Item Models for Application & Desktop UI
# ---------------------------------------------------------------------------

class ProvinceOption(BaseModel):
    id: int
    code: str
    label: str
    stateProvinceCode: int
    stateProvinceDesc: str


class DocTypeOption(BaseModel):
    id: int
    code: str
    label: str
    docTypeId: int
    docDescription: str


class ItemCodeOption(BaseModel):
    id: str
    code: str
    label: str
    hS_CODE: str
    description: str


class SroItemDictOption(BaseModel):
    id: int
    code: str
    label: str
    srO_ITEM_ID: int
    srO_ITEM_DESC: str


class TransactionTypeOption(BaseModel):
    id: int
    code: str
    label: str
    transactioN_TYPE_ID: int
    transactioN_DESC: str


class UomOption(BaseModel):
    id: int
    code: str
    label: str
    uoM_ID: int
    description: str


class SroScheduleOption(BaseModel):
    id: int
    code: str
    label: str
    srO_ID: int
    srO_DESC: str


class SaleTypeRateOption(BaseModel):
    id: int
    code: str
    label: str
    rate_value: float
    ratE_ID: int
    ratE_DESC: str
    ratE_VALUE: float


class HsUomOption(BaseModel):
    id: int
    code: str
    label: str
    annexure_id: int
    uoM_ID: int
    description: str


class SroItemByScheduleOption(BaseModel):
    id: int
    code: str
    label: str
    sro_id: int
    srO_ITEM_ID: int
    srO_ITEM_DESC: str


class StatlStatusResult(BaseModel):
    regno: str
    date: str
    status_code: Optional[str] = None
    status: str = "not_checked"  # Active | In-Active | not_checked | unknown
    is_active: Optional[bool] = None
    verified_state: str = "not_checked"  # verified_active | verified_inactive | not_checked | unknown
    raw_response: Dict[str, Any] = Field(default_factory=dict)


class RegistrationTypeResult(BaseModel):
    registration_no: str
    statuscode: Optional[str] = None
    REGISTRATION_NO: str
    REGISTRATION_TYPE: str = "unknown"  # Registered | Unregistered | unknown | not_checked
    normalized_type: str = "unknown"  # Registered | Unregistered | unknown | not_checked
    verified_state: str = "not_checked"  # verified_registered | verified_unregistered | not_checked | unknown
    raw_response: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 3. Provenance Envelope & Admin Sync Status Contracts
# ---------------------------------------------------------------------------

T = TypeVar("T")


class ReferenceEnvelope(BaseModel, Generic[T]):
    """Standardized response envelope with explicit provenance and cache freshness."""
    data: T
    items: Optional[Any] = None  # Legacy compatibility alias for desktop callers
    count: int = 0
    catalog_key: str
    source: str = DataSourceTag.DEMO_FIXTURE.value
    source_version: str = "1.12"
    provider_mode: str = ProviderMode.FIXTURE.value
    official_live_verified: bool = False
    as_of: Optional[str] = None
    effective_date: Optional[str] = None
    stale: bool = False
    last_sync_error: Optional[str] = None
    transport_mode: Optional[str] = None
    request_fingerprint: Optional[str] = None
    warning: Optional[str] = None


class CatalogDatasetStatus(BaseModel):
    catalog_key: str
    section: str
    endpoint_path: str
    cached_count: int = 0
    source: str = DataSourceTag.DEMO_FIXTURE.value
    official_live_verified: bool = False
    last_fetched_at: Optional[str] = None
    expires_at: Optional[str] = None
    stale: bool = False
    last_error: Optional[str] = None


class ReferenceReadinessResponse(BaseModel):
    pral_token_configured: bool = False
    default_provider_mode: str = ProviderMode.FIXTURE.value
    statl_transport_strategy: str = StatlTransportStrategy.QUERY_PARAMS.value
    official_live_verified_count: int = 0
    total_endpoints: int = 12
    datasets: List[CatalogDatasetStatus] = Field(default_factory=list)
    recent_sync_runs: List[Dict[str, Any]] = Field(default_factory=list)
