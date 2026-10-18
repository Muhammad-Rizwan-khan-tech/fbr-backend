"""PRAL Digital Invoicing v1.12 Reference API Routes (Section 5, pages 22-34).

Exposes:
  1. Canonical enveloped endpoints under `/api/v1/fbr/references/*` and `/api/v1/fbr/registration/*`
     returning `ReferenceEnvelope` with explicit provenance (`source`, `official_live_verified`,
     `as_of`, `stale`, `last_sync_error`, `warning`).
  2. Super Admin readiness & sync endpoints under `/api/v1/admin/fbr/*`.
  3. Backward-compatible routes under `/api/v1/reference/fbr/*` for existing callers.
"""

from typing import Any, Dict, Optional, Union
from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.dependencies import get_current_user, require_admin_access
from backend.app.core.pral_error_codes import PRAL_ERROR_REGISTRY
from backend.app.core.pral_scenarios import (
    PRAL_SCENARIOS_REGISTRY,
    get_scenarios_for_activity,
)
from backend.app.models.user import User
from backend.app.schemas.pral_reference import (
    ProviderMode,
    ReferenceEnvelope,
    ReferenceReadinessResponse,
    StatlTransportStrategy,
)
from backend.app.services.pral_reference_service import pral_reference_service

router = APIRouter(tags=["PRAL Official Reference Data"])


class StatlLookupRequest(BaseModel):
    regno: str
    date: Optional[str] = None
    provider_mode: Optional[ProviderMode] = None
    transport_strategy: Optional[StatlTransportStrategy] = None


class RegTypeLookupRequest(BaseModel):
    Registration_No: str
    provider_mode: Optional[ProviderMode] = None
    transport_strategy: Optional[StatlTransportStrategy] = None


class AdminReferenceSyncRequest(BaseModel):
    provider_mode: Optional[ProviderMode] = None
    tenant_id: Optional[str] = None
    organization_id: Optional[str] = None


# ===========================================================================
# 1. Canonical PRAL v1.12 Enveloped Reference Endpoints (/fbr/references/*)
# ===========================================================================

@router.get("/fbr/references/provinces", response_model=ReferenceEnvelope)
async def fbr_get_provinces(
    provider_mode: Optional[ProviderMode] = Query(None),
    mode: Optional[ProviderMode] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Section 5.1: GET /pdi/v1/provinces — Official PRAL Province Codes."""
    return await pral_reference_service.fetch_provinces_envelope(
        provider_mode=provider_mode or mode, db=db, tenant_id=current_user.tenant_id
    )


@router.get("/fbr/references/document-types", response_model=ReferenceEnvelope)
async def fbr_get_document_types(
    provider_mode: Optional[ProviderMode] = Query(None),
    mode: Optional[ProviderMode] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Section 5.2: GET /pdi/v1/doctypecode — Official PRAL Document Type IDs."""
    return await pral_reference_service.fetch_document_types_envelope(
        provider_mode=provider_mode or mode, db=db, tenant_id=current_user.tenant_id
    )


@router.get("/fbr/references/item-codes", response_model=ReferenceEnvelope)
async def fbr_get_item_codes(
    q: Optional[str] = Query(None, description="Local search filter over cached HS/item catalog"),
    search: Optional[str] = Query(None, description="Alias for q"),
    limit: int = Query(100, ge=0, le=2000),
    offset: int = Query(0, ge=0),
    provider_mode: Optional[ProviderMode] = Query(None),
    mode: Optional[ProviderMode] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Section 5.3: GET /pdi/v1/itemdesccode — Official PRAL Item/HS Code Catalog (no upstream params)."""
    return await pral_reference_service.fetch_item_codes_envelope(
        search=q or search,
        limit=limit,
        offset=offset,
        provider_mode=provider_mode or mode,
        db=db,
        tenant_id=current_user.tenant_id,
    )


@router.get("/fbr/references/sro-item-codes", response_model=ReferenceEnvelope)
async def fbr_get_sro_item_codes(
    q: Optional[str] = Query(None),
    limit: int = Query(100, ge=0, le=2000),
    offset: int = Query(0, ge=0),
    provider_mode: Optional[ProviderMode] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Section 5.4: GET /pdi/v1/sroitemcode — Official PRAL SRO Item ID Dictionary."""
    return await pral_reference_service.fetch_sro_item_codes_envelope(
        search=q,
        limit=limit,
        offset=offset,
        provider_mode=provider_mode,
        db=db,
        tenant_id=current_user.tenant_id,
    )


@router.get("/fbr/references/transaction-types", response_model=ReferenceEnvelope)
async def fbr_get_transaction_types(
    provider_mode: Optional[ProviderMode] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Section 5.5: GET /pdi/v1/transtypecode — Official PRAL Transaction Type IDs."""
    return await pral_reference_service.fetch_transaction_types_envelope(
        provider_mode=provider_mode, db=db, tenant_id=current_user.tenant_id
    )


@router.get("/fbr/references/uoms", response_model=ReferenceEnvelope)
async def fbr_get_uoms(
    provider_mode: Optional[ProviderMode] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Section 5.6: GET /pdi/v1/uom — Official PRAL Units of Measurement."""
    return await pral_reference_service.fetch_uoms_envelope(
        provider_mode=provider_mode, db=db, tenant_id=current_user.tenant_id
    )


@router.get("/fbr/references/sro-schedules", response_model=ReferenceEnvelope)
async def fbr_get_sro_schedules(
    rate_id: int = Query(..., description="Selected Rate ID from SaleTypeToRate"),
    date: Optional[str] = Query(None, description="Invoice date (YYYY-MM-DD or DD-Mon-YYYY)"),
    origination_supplier_csv: Union[int, str] = Query(1, description="Seller province code / origination supplier CSV"),
    provider_mode: Optional[ProviderMode] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Section 5.7: GET /pdi/v1/SroSchedule?rate_id=...&date=DD-Mon-YYYY&origination_supplier_csv=..."""
    return await pral_reference_service.fetch_sro_schedules_envelope(
        rate_id=rate_id,
        date=date,
        origination_supplier_csv=origination_supplier_csv,
        provider_mode=provider_mode,
        db=db,
        tenant_id=current_user.tenant_id,
    )


@router.get("/fbr/references/sale-type-rates", response_model=ReferenceEnvelope)
async def fbr_get_sale_type_rates(
    trans_type_id: Optional[int] = Query(None, description="Transaction Type ID"),
    transTypeId: Optional[int] = Query(None, description="PRAL wire alias for trans_type_id"),
    origination_supplier: Optional[int] = Query(None, description="Seller Province ID"),
    originationSupplier: Optional[int] = Query(None, description="PRAL wire alias for origination_supplier"),
    date: Optional[str] = Query(None, description="Invoice date (YYYY-MM-DD or DD-Mon-YYYY)"),
    provider_mode: Optional[ProviderMode] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Section 5.8: GET /pdi/v2/SaleTypeToRate?date=DD-Mon-YYYY&transTypeId=...&originationSupplier=..."""
    resolved_tt = trans_type_id if trans_type_id is not None else (transTypeId if transTypeId is not None else 75)
    resolved_prov = (
        origination_supplier
        if origination_supplier is not None
        else (originationSupplier if originationSupplier is not None else 7)
    )
    return await pral_reference_service.fetch_sale_type_rates_envelope(
        trans_type_id=resolved_tt,
        origination_supplier=resolved_prov,
        date=date,
        provider_mode=provider_mode,
        db=db,
        tenant_id=current_user.tenant_id,
    )


@router.get("/fbr/references/hs-uom", response_model=ReferenceEnvelope)
async def fbr_get_hs_uom(
    hs_code: str = Query(..., description="HS Code e.g. 5904.9000"),
    annexure_id: int = Query(3, description="Sales tax annexure ID (default 3)"),
    provider_mode: Optional[ProviderMode] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Section 5.9: GET /pdi/v2/HS_UOM?hs_code=...&annexure_id=..."""
    return await pral_reference_service.fetch_hs_uom_envelope(
        hs_code=hs_code,
        annexure_id=annexure_id,
        provider_mode=provider_mode,
        db=db,
        tenant_id=current_user.tenant_id,
    )


@router.get("/fbr/references/sro-items", response_model=ReferenceEnvelope)
async def fbr_get_sro_items_by_schedule(
    sro_id: int = Query(..., description="SRO Schedule ID from Section 5.7"),
    date: Optional[str] = Query(None, description="Invoice date (YYYY-MM-DD)"),
    provider_mode: Optional[ProviderMode] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Section 5.10: GET /pdi/v2/SROItem?date=YYYY-MM-DD&sro_id=..."""
    return await pral_reference_service.fetch_sro_items_by_schedule_envelope(
        sro_id=sro_id,
        date=date,
        provider_mode=provider_mode,
        db=db,
        tenant_id=current_user.tenant_id,
    )


@router.post("/fbr/registration/statl", response_model=ReferenceEnvelope)
async def fbr_post_statl(
    body: StatlLookupRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Section 5.11: STATL active taxpayer lookup (supports selectable transport strategy)."""
    return await pral_reference_service.check_statl_envelope(
        regno=body.regno,
        date=body.date,
        provider_mode=body.provider_mode,
        transport_strategy=body.transport_strategy,
        db=db,
        tenant_id=current_user.tenant_id,
    )


@router.get("/fbr/registration/statl", response_model=ReferenceEnvelope)
async def fbr_get_statl(
    regno: str = Query(..., description="7-digit NTN or 13-digit CNIC"),
    date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    provider_mode: Optional[ProviderMode] = Query(None),
    transport_strategy: Optional[StatlTransportStrategy] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Section 5.11: GET /dist/v1/statl — STATL active taxpayer lookup."""
    return await pral_reference_service.check_statl_envelope(
        regno=regno,
        date=date,
        provider_mode=provider_mode,
        transport_strategy=transport_strategy,
        db=db,
        tenant_id=current_user.tenant_id,
    )


@router.post("/fbr/registration/type", response_model=ReferenceEnvelope)
async def fbr_post_registration_type(
    body: RegTypeLookupRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Section 5.12: Get_Reg_Type buyer registration type lookup."""
    return await pral_reference_service.check_registration_type_envelope(
        registration_no=body.Registration_No,
        provider_mode=body.provider_mode,
        transport_strategy=body.transport_strategy,
        db=db,
        tenant_id=current_user.tenant_id,
    )


@router.get("/fbr/registration/type", response_model=ReferenceEnvelope)
async def fbr_get_registration_type(
    Registration_No: str = Query(..., description="7-digit NTN or 13-digit CNIC"),
    provider_mode: Optional[ProviderMode] = Query(None),
    transport_strategy: Optional[StatlTransportStrategy] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Section 5.12: GET /dist/v1/Get_Reg_Type — Buyer registration type lookup."""
    return await pral_reference_service.check_registration_type_envelope(
        registration_no=Registration_No,
        provider_mode=provider_mode,
        transport_strategy=transport_strategy,
        db=db,
        tenant_id=current_user.tenant_id,
    )


@router.get("/fbr/references/readiness", response_model=ReferenceReadinessResponse)
def fbr_get_tenant_reference_readiness(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Desktop/Tenant readiness summary showing token presence, provenance, and cache freshness."""
    return pral_reference_service.get_reference_readiness(db=db, tenant_id=current_user.tenant_id)


# ===========================================================================
# 2. Super Admin Reference Status & Manual Sync Endpoints (/admin/fbr/*)
# ===========================================================================

@router.get("/admin/fbr/reference-status", response_model=ReferenceReadinessResponse)
def admin_get_fbr_reference_status(
    tenant_id: Optional[str] = Query(None),
    organization_id: Optional[str] = Query(None),
    admin: str = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Super Admin inspection of all 12 PRAL reference catalogs, provenance, and sync history."""
    return pral_reference_service.get_reference_readiness(db=db, tenant_id=tenant_id or organization_id)


@router.post("/admin/fbr/reference-sync")
async def admin_sync_fbr_reference_catalogs(
    body: Optional[AdminReferenceSyncRequest] = Body(default=None),
    admin: str = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Super Admin manual sync trigger for PRAL master reference dictionaries."""
    req = body or AdminReferenceSyncRequest()
    return await pral_reference_service.sync_master_catalogs(
        db=db,
        provider_mode=req.provider_mode,
        tenant_id=req.tenant_id or req.organization_id,
        triggered_by=f"admin:{admin}",
    )


# ===========================================================================
# 3. Backward-Compatible Routes (/reference/fbr/*)
# ===========================================================================

@router.get("/reference/fbr/provinces")
async def get_provinces(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GET /pdi/v1/provinces — Official PRAL Provinces."""
    return await pral_reference_service.get_provinces(db=db, tenant_id=current_user.tenant_id)


@router.get("/reference/fbr/doc-types")
async def get_document_types(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GET /pdi/v1/doctypecode — Official PRAL Document Types."""
    return await pral_reference_service.get_document_types(db=db, tenant_id=current_user.tenant_id)


@router.get("/reference/fbr/hs-codes")
async def get_hs_codes(
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GET /pdi/v1/itemdesccode — Official PRAL 8-digit HS Code Catalog."""
    return await pral_reference_service.get_hs_codes(
        search=search, db=db, tenant_id=current_user.tenant_id
    )


@router.get("/reference/fbr/sro-item-codes")
async def get_sro_item_codes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GET /pdi/v1/sroitemcode — Official PRAL SRO Item Code Dictionary."""
    return await pral_reference_service.get_sro_item_codes(db=db, tenant_id=current_user.tenant_id)


@router.get("/reference/fbr/uoms")
async def get_uoms(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GET /pdi/v1/uom — Official PRAL Units of Measurement."""
    return await pral_reference_service.get_uoms(db=db, tenant_id=current_user.tenant_id)


@router.get("/reference/fbr/transaction-types")
async def get_transaction_types(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GET /pdi/v1/transtypecode — Official PRAL Transaction / Sale Types."""
    return await pral_reference_service.get_transaction_types(db=db, tenant_id=current_user.tenant_id)


@router.get("/reference/fbr/sro-schedules")
async def get_sro_schedules(
    rate_id: int = Query(701),
    date: Optional[str] = Query(None),
    origination_supplier_csv: Union[int, str] = Query(1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GET /pdi/v1/SroSchedule — Official PRAL SRO Schedules."""
    return await pral_reference_service.get_sro_schedules(
        rate_id=rate_id,
        date=date,
        origination_supplier_csv=origination_supplier_csv,
        db=db,
        tenant_id=current_user.tenant_id,
    )


@router.get("/reference/fbr/hs-uom")
async def get_uoms_for_hs_code(
    hs_code: str = Query(..., description="8-digit HS Code"),
    annexure_id: int = Query(3, description="Sales tax annexure ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GET /pdi/v2/HS_UOM — Allowed UOMs for a given HS code and annexure ID."""
    return await pral_reference_service.get_valid_uoms_for_hs_code(
        hs_code=hs_code, annexure_id=annexure_id, db=db, tenant_id=current_user.tenant_id
    )


@router.get("/reference/fbr/rates")
async def get_rates(
    sale_type: str = Query(..., description="PRAL Sale Type"),
    province: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    trans_type_id: Optional[int] = Query(None),
    origination_supplier: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GET /pdi/v2/SaleTypeToRate — Dynamic Rate Lookup by Sale Type."""
    rates = await pral_reference_service.get_rates_for_sale_type(
        sale_type=sale_type,
        date=date,
        province=province,
        trans_type_id=trans_type_id,
        origination_supplier=origination_supplier,
        db=db,
        tenant_id=current_user.tenant_id,
    )
    return {"sale_type": sale_type, "applicable_rates": rates}


@router.get("/reference/fbr/sro-items")
async def get_sro_items(
    sro_id: int = Query(..., description="SRO Schedule ID"),
    date: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GET /pdi/v2/SROItem — SRO Item lookup by Schedule ID and Date."""
    return await pral_reference_service.get_sro_items_by_schedule(
        sro_schedule_no=sro_id, date=date, db=db, tenant_id=current_user.tenant_id
    )


@router.get("/reference/fbr/statl")
async def check_statl(
    ntn: str = Query(..., description="7-digit NTN or 13-digit CNIC"),
    date: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GET /dist/v1/statl — Sales Tax Active Taxpayer List Verification."""
    return await pral_reference_service.check_statl_status(
        ntn_or_cnic=ntn, date=date, db=db, tenant_id=current_user.tenant_id
    )


@router.get("/reference/fbr/reg-type")
async def check_reg_type(
    registration_no: str = Query(..., description="7-digit NTN or 13-digit CNIC"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GET /dist/v1/Get_Reg_Type — Buyer Registration Type Verification."""
    return await pral_reference_service.get_registration_types(
        registration_no=registration_no, db=db, tenant_id=current_user.tenant_id
    )


@router.get("/reference/fbr/scenarios")
def get_sandbox_scenarios(
    business_activity: Optional[str] = Query(None, description="Optional sector filter"),
    current_user: User = Depends(get_current_user),
):
    """Section 9 & 10: 28 PRAL Sandbox Scenarios SN001–SN028 filtered by sector eligibility."""
    if business_activity:
        scenarios = get_scenarios_for_activity(business_activity)
    else:
        scenarios = list(PRAL_SCENARIOS_REGISTRY.values())
    return [s.to_dict() for s in scenarios]


@router.get("/reference/fbr/error-codes")
def get_error_codes(current_user: User = Depends(get_current_user)):
    """Section 7 & 8: Structured Sales & Purchase Error Codes Dictionary."""
    return [e.to_dict() for e in PRAL_ERROR_REGISTRY.values()]
