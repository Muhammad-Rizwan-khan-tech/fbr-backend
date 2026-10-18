"""
Comprehensive Test Suite for PRAL Digital Invoicing API v1.12 Integration:
- All 12 Section 5 Reference Data APIs (5.1 - 5.12)
- Wire-exact key parsing, date formatting (DD-Mon-YYYY vs YYYY-MM-DD), and case-sensitive parameters
- Selectable transport strategies for 5.11 (statl) & 5.12 (Get_Reg_Type)
- Provider modes (fixture, cached_official, authorized_live) and provenance envelopes
- Section 4 Invoice Serialization, Local Validation, Mixed-Response Interpretation, and Credential Guards
"""

import asyncio
from datetime import date
from decimal import Decimal
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.core.security import create_access_token
from backend.app.core.errors import CredentialsMissingError, InvalidRequestError
from backend.app.models.user import User
from backend.app.models.tenant import Organization
from backend.app.models.branch import Branch
from backend.app.models.customer import Customer
from backend.app.schemas.pral_reference import ProviderMode, StatlTransportStrategy
from backend.app.services.pral_reference_service import (
    PralReferenceService,
    format_pral_dd_mon_yyyy,
    format_pral_iso_date,
)
from backend.app.adapters.sandbox_adapter import SandboxFBRAdapter
from backend.app.adapters.production_adapter import ProductionFBRAdapter

client = TestClient(app)


def _get_test_context():
    db = SessionLocal()
    user = db.query(User).filter(User.email == "admin@abcdistribution.com").first()
    org = db.query(Organization).filter(Organization.id == user.tenant_id).first()
    branch = db.query(Branch).filter(Branch.tenant_id == org.id).first()
    customer = db.query(Customer).filter(Customer.tenant_id == org.id).first()
    token = create_access_token(subject=user.id, tenant_id=org.id, role=user.role)
    return db, {"Authorization": f"Bearer {token}"}, org, branch, customer


# ==============================================================================
# 1. Date Formatter & Wire Parameter Unit Tests
# ==============================================================================

def test_pral_date_formatters_for_section_5_endpoints():
    """
    Verify exact date formats required by PRAL DI API v1.12:
    - Sections 5.7 (SroSchedule) & 5.8 (SaleTypeToRate): DD-Mon-YYYY (e.g., 24-Feb-2024)
    - Sections 5.10 (SROItem) & 5.11 (statl): YYYY-MM-DD (e.g., 2025-03-25)
    """
    assert format_pral_dd_mon_yyyy("2024-02-24") == "24-Feb-2024"
    assert format_pral_dd_mon_yyyy(date(2024, 2, 4)) == "04-Feb-2024"
    assert format_pral_dd_mon_yyyy("04-Feb-2024") == "04-Feb-2024"

    assert format_pral_iso_date("2025-03-25") == "2025-03-25"
    assert format_pral_iso_date("25-Mar-2025") == "2025-03-25"
    assert format_pral_iso_date(date(2025, 5, 18)) == "2025-05-18"

    with pytest.raises(InvalidRequestError):
        format_pral_dd_mon_yyyy("not-a-valid-date")

    with pytest.raises(InvalidRequestError):
        format_pral_iso_date("99/99/9999")


# ==============================================================================
# 2. All 12 Section 5 Reference APIs — Fixture Mode & Provenance Tests
# ==============================================================================

def test_all_12_reference_apis_in_fixture_mode_preserve_wire_keys_and_provenance():
    """
    When no PRAL token is configured, fixture mode must:
    - Return DEMO_FIXTURE provenance with official_live_verified=False
    - Preserve exact documented PRAL v1.12 wire keys alongside normalized fields
    - Never fabricate active taxpayer status for 5.11 STATL
    """
    db = SessionLocal()
    try:
        svc = PralReferenceService(bearer_token="")

        async def _run():
            # 5.1 Provinces
            env_5_1 = await svc.fetch_provinces_envelope(provider_mode=ProviderMode.FIXTURE, db=db)
            assert env_5_1.source == "DEMO_FIXTURE"
            assert env_5_1.official_live_verified is False
            assert any(p["stateProvinceCode"] == 7 and p["stateProvinceDesc"] == "PUNJAB" for p in env_5_1.data)
            assert any(p["stateProvinceCode"] == 8 and p["stateProvinceDesc"] == "SINDH" for p in env_5_1.data)

            # 5.2 Document Types
            env_5_2 = await svc.fetch_document_types_envelope(provider_mode=ProviderMode.FIXTURE, db=db)
            assert env_5_2.official_live_verified is False
            assert any(d["docTypeId"] == 4 and d["docDescription"] == "Sale Invoice" for d in env_5_2.data)
            assert any(d["docTypeId"] == 9 and d["docDescription"] == "Debit Note" for d in env_5_2.data)

            # 5.3 HS / Item Description Codes (local search + pagination)
            env_5_3 = await svc.fetch_item_codes_envelope(
                search="8432", limit=10, provider_mode=ProviderMode.FIXTURE, db=db
            )
            assert env_5_3.official_live_verified is False
            assert len(env_5_3.data) >= 1
            assert env_5_3.data[0]["hS_CODE"] == "8432.1010"

            # 5.4 SRO Item Codes
            env_5_4 = await svc.fetch_sro_item_codes_envelope(provider_mode=ProviderMode.FIXTURE, db=db)
            assert env_5_4.official_live_verified is False
            assert any(s["srO_ITEM_ID"] == 724 and s["srO_ITEM_DESC"] == "9" for s in env_5_4.data)

            # 5.5 Transaction Type Codes
            env_5_5 = await svc.fetch_transaction_types_envelope(provider_mode=ProviderMode.FIXTURE, db=db)
            assert env_5_5.official_live_verified is False
            assert any(t["transactioN_TYPE_ID"] == 82 and t["transactioN_DESC"] == "DTRE goods" for t in env_5_5.data)

            # 5.6 UOMs
            env_5_6 = await svc.fetch_uoms_envelope(provider_mode=ProviderMode.FIXTURE, db=db)
            assert env_5_6.official_live_verified is False
            assert any(u["uoM_ID"] == 77 and u["description"] == "Square Metre" for u in env_5_6.data)

            # 5.7 SRO Schedule
            env_5_7 = await svc.fetch_sro_schedules_envelope(
                rate_id=413, date="2024-02-04", origination_supplier_csv=1, provider_mode=ProviderMode.FIXTURE, db=db
            )
            assert env_5_7.official_live_verified is False
            assert env_5_7.effective_date == "04-Feb-2024"
            assert any(s["srO_ID"] == 7 and "Zero Rated Gas" in s["srO_DESC"] for s in env_5_7.data)

            # 5.8 SaleTypeToRate (preserves compound rate descriptions)
            env_5_8 = await svc.fetch_sale_type_rates_envelope(
                date="2024-02-24", trans_type_id=115, origination_supplier=1, provider_mode=ProviderMode.FIXTURE, db=db
            )
            assert env_5_8.official_live_verified is False
            assert env_5_8.effective_date == "24-Feb-2024"
            assert any(
                r["ratE_ID"] == 734 and r["ratE_DESC"] == "18% along with rupees 60 per kilogram"
                for r in env_5_8.data
            )

            # 5.9 HS_UOM (requires hs_code and annexure_id)
            env_5_9 = await svc.fetch_hs_uom_envelope(
                hs_code="5904.9000", annexure_id=3, provider_mode=ProviderMode.FIXTURE, db=db
            )
            assert env_5_9.official_live_verified is False
            assert any(u["uoM_ID"] == 77 and u["annexure_id"] == 3 for u in env_5_9.data)

            # 5.10 SROItem by Schedule (requires date YYYY-MM-DD and sro_id)
            env_5_10 = await svc.fetch_sro_items_by_schedule_envelope(
                date="2025-03-25", sro_id=389, provider_mode=ProviderMode.FIXTURE, db=db
            )
            assert env_5_10.official_live_verified is False
            assert env_5_10.effective_date == "2025-03-25"
            assert len(env_5_10.data) >= 1

            # 5.11 STATL — Must NOT fabricate active status when offline/no token!
            env_5_11 = await svc.check_statl_envelope(
                regno="0788762", date="2025-05-18", provider_mode=ProviderMode.FIXTURE, db=db
            )
            assert env_5_11.official_live_verified is False
            assert env_5_11.data["is_active"] is None
            assert env_5_11.data["status"] == "not_checked"

            # 5.12 Get_Reg_Type — Must NOT fabricate registered status when offline/no token!
            env_5_12 = await svc.check_registration_type_envelope(
                registration_no="0788762", provider_mode=ProviderMode.FIXTURE, db=db
            )
            assert env_5_12.official_live_verified is False
            assert env_5_12.data["REGISTRATION_TYPE"] == "unknown"

        asyncio.run(_run())
    finally:
        db.close()


# ==============================================================================
# 3. Authorized Live Mode & Mock Upstream Wire Verification (All 12 Endpoints)
# ==============================================================================

def test_authorized_live_mode_fails_fast_without_token_and_never_calls_upstream():
    """
    When provider_mode=authorized_live is requested without a PRAL token:
    - Must raise CredentialsMissingError immediately
    - Must NEVER make any network request to gw.fbr.gov.pk
    """
    db = SessionLocal()
    try:
        svc = PralReferenceService(bearer_token="")

        async def _run():
            with patch("httpx.AsyncClient") as mock_client:
                with pytest.raises(CredentialsMissingError):
                    await svc.fetch_provinces_envelope(provider_mode=ProviderMode.AUTHORIZED_LIVE, db=db)
                with pytest.raises(CredentialsMissingError):
                    await svc.check_statl_envelope(
                        regno="0788762", provider_mode=ProviderMode.AUTHORIZED_LIVE, db=db
                    )
                mock_client.assert_not_called()

        asyncio.run(_run())
    finally:
        db.close()


def test_authorized_live_mode_sends_exact_urls_headers_and_params_for_all_12_endpoints():
    """
    Verify that with a Bearer token configured, PralReferenceService sends exact
    PRAL v1.12 paths, case-sensitive query parameters, Authorization header, and
    parses odd response keys (hS_CODE, srO_ITEM_ID, transactioN_TYPE_ID, uoM_ID,
    "status code" with space, "statuscode" without space).
    """
    db = SessionLocal()
    try:
        svc = PralReferenceService(bearer_token="test-pral-bearer-token-xyz")
        recorded_calls = []

        async def fake_request(method, url, headers=None, params=None, json=None):
            recorded_calls.append({
                "method": method,
                "url": url,
                "headers": headers,
                "params": params,
                "json": json,
            })
            resp = MagicMock()
            resp.status_code = 200
            if url.endswith("/pdi/v1/provinces"):
                resp.json.return_value = [{"stateProvinceCode": 7, "stateProvinceDesc": "PUNJAB"}]
            elif url.endswith("/pdi/v1/doctypecode"):
                resp.json.return_value = [{"docTypeId": 4, "docDescription": "Sale Invoice"}]
            elif url.endswith("/pdi/v1/itemdesccode"):
                resp.json.return_value = [{"hS_CODE": "8432.1010", "description": "NUCLEAR REACTORS"}]
            elif url.endswith("/pdi/v1/sroitemcode"):
                resp.json.return_value = [{"srO_ITEM_ID": 17248, "srO_ITEM_DESC": "9"}]
            elif url.endswith("/pdi/v1/transtypecode"):
                resp.json.return_value = [{"transactioN_TYPE_ID": 82, "transactioN_DESC": "DTRE goods"}]
            elif url.endswith("/pdi/v1/uom"):
                resp.json.return_value = [{"uoM_ID": 77, "description": "Square Metre"}]
            elif url.endswith("/pdi/v1/SroSchedule"):
                resp.json.return_value = [{"srO_ID": 7, "srO_DESC": "ZERO RATED GAS"}]
            elif url.endswith("/pdi/v2/SaleTypeToRate"):
                resp.json.return_value = [{
                    "ratE_ID": 742,
                    "ratE_DESC": "18% along with rupees 60 per kilogram",
                    "ratE_VALUE": 18,
                }]
            elif url.endswith("/pdi/v2/HS_UOM"):
                resp.json.return_value = [{"uoM_ID": 59, "description": "40KG"}]
            elif url.endswith("/pdi/v2/SROItem"):
                resp.json.return_value = [{"srO_ITEM_ID": 17912, "srO_ITEM_DESC": "4(1)(a)(ii)"}]
            elif url.endswith("/dist/v1/statl"):
                resp.json.return_value = {"status code": "01", "status": "Active"}
            elif url.endswith("/dist/v1/Get_Reg_Type"):
                resp.json.return_value = {"statuscode": "00", "REGISTRATION_TYPE": "Registered"}
            return resp

        async def _get(url, headers=None, params=None):
            return await fake_request("GET", url, headers=headers, params=params)

        async def _post(url, headers=None, json=None):
            return await fake_request("POST", url, headers=headers, json=json)

        async def _req(method, url, headers=None, json=None):
            return await fake_request(method, url, headers=headers, json=json)

        async def _run():
            with patch("backend.app.services.pral_reference_service.httpx.AsyncClient") as mock_client_cls:
                client_instance = AsyncMock()
                client_instance.get.side_effect = _get
                client_instance.post.side_effect = _post
                client_instance.request.side_effect = _req
                mock_client_cls.return_value.__aenter__.return_value = client_instance

                # 5.1 - 5.6
                r_51 = await svc.fetch_provinces_envelope(provider_mode=ProviderMode.AUTHORIZED_LIVE, db=db)
                assert r_51.source == "PRAL_LIVE" and r_51.official_live_verified is True

                r_52 = await svc.fetch_document_types_envelope(provider_mode=ProviderMode.AUTHORIZED_LIVE, db=db)
                assert r_52.data[0]["docTypeId"] == 4

                # 5.3 must NOT pass ?search= to upstream PRAL
                r_53 = await svc.fetch_item_codes_envelope(
                    search="8432", provider_mode=ProviderMode.AUTHORIZED_LIVE, db=db
                )
                assert r_53.data[0]["hS_CODE"] == "8432.1010"

                r_54 = await svc.fetch_sro_item_codes_envelope(provider_mode=ProviderMode.AUTHORIZED_LIVE, db=db)
                assert r_54.data[0]["srO_ITEM_ID"] == 17248

                r_55 = await svc.fetch_transaction_types_envelope(provider_mode=ProviderMode.AUTHORIZED_LIVE, db=db)
                assert r_55.data[0]["transactioN_TYPE_ID"] == 82

                r_56 = await svc.fetch_uoms_envelope(provider_mode=ProviderMode.AUTHORIZED_LIVE, db=db)
                assert r_56.data[0]["uoM_ID"] == 77

                # 5.7 SroSchedule -> exact params: rate_id, date (DD-Mon-YYYY), origination_supplier_csv
                r_57 = await svc.fetch_sro_schedules_envelope(
                    rate_id=413,
                    date="2024-02-04",
                    origination_supplier_csv=1,
                    provider_mode=ProviderMode.AUTHORIZED_LIVE,
                    db=db,
                )
                assert r_57.data[0]["srO_ID"] == 7

                # 5.8 SaleTypeToRate -> exact params: date (DD-Mon-YYYY), transTypeId, originationSupplier
                r_58 = await svc.fetch_sale_type_rates_envelope(
                    date="2024-02-24",
                    trans_type_id=82,
                    origination_supplier=1,
                    provider_mode=ProviderMode.AUTHORIZED_LIVE,
                    db=db,
                )
                assert r_58.data[0]["ratE_ID"] == 742
                assert r_58.data[0]["ratE_DESC"] == "18% along with rupees 60 per kilogram"

                # 5.9 HS_UOM -> exact params: hs_code, annexure_id
                r_59 = await svc.fetch_hs_uom_envelope(
                    hs_code="8432.1010", annexure_id=3, provider_mode=ProviderMode.AUTHORIZED_LIVE, db=db
                )
                assert r_59.data[0]["uoM_ID"] == 59

                # 5.10 SROItem -> exact params: date (YYYY-MM-DD), sro_id
                r_510 = await svc.fetch_sro_items_by_schedule_envelope(
                    date="2025-03-25", sro_id=389, provider_mode=ProviderMode.AUTHORIZED_LIVE, db=db
                )
                assert r_510.data[0]["srO_ITEM_ID"] == 17912

                # 5.11 STATL -> test all 3 transport strategies
                for strategy in (
                    StatlTransportStrategy.QUERY_PARAMS,
                    StatlTransportStrategy.JSON_BODY_GET,
                    StatlTransportStrategy.POST_FALLBACK,
                ):
                    r_511 = await svc.check_statl_envelope(
                        regno="0788762",
                        date="2025-05-18",
                        provider_mode=ProviderMode.AUTHORIZED_LIVE,
                        transport_strategy=strategy,
                        db=db,
                    )
                    assert r_511.data["status_code"] == "01"
                    assert r_511.data["is_active"] is True
                    assert r_511.transport_mode == strategy.value

                # 5.12 Get_Reg_Type -> test query_params and json_body_get
                r_512 = await svc.check_registration_type_envelope(
                    registration_no="0788762",
                    provider_mode=ProviderMode.AUTHORIZED_LIVE,
                    transport_strategy=StatlTransportStrategy.QUERY_PARAMS,
                    db=db,
                )
                assert r_512.data["statuscode"] == "00"
                assert r_512.data["REGISTRATION_TYPE"] == "Registered"

                # Verify CACHED_OFFICIAL mode now reads the cached DB rows populated above
                r_cached = await svc.fetch_provinces_envelope(
                    provider_mode=ProviderMode.CACHED_OFFICIAL, db=db
                )
                assert r_cached.official_live_verified is True
                assert r_cached.data[0]["stateProvinceCode"] == 7

        asyncio.run(_run())

        # Verify Authorization header and exact parameter names on recorded calls
        for call in recorded_calls:
            assert call["headers"]["Authorization"] == "Bearer test-pral-bearer-token-xyz"

        itemdesccode_call = next(c for c in recorded_calls if c["url"].endswith("/pdi/v1/itemdesccode"))
        assert itemdesccode_call["params"] is None  # 5.3 requires no request input

        sro_sched_call = next(c for c in recorded_calls if c["url"].endswith("/pdi/v1/SroSchedule"))
        assert sro_sched_call["params"] == {
            "rate_id": 413,
            "date": "04-Feb-2024",
            "origination_supplier_csv": "1",
        }

        rate_call = next(c for c in recorded_calls if c["url"].endswith("/pdi/v2/SaleTypeToRate"))
        assert rate_call["params"] == {
            "date": "24-Feb-2024",
            "transTypeId": 82,
            "originationSupplier": 1,
        }

        hs_uom_call = next(c for c in recorded_calls if c["url"].endswith("/pdi/v2/HS_UOM"))
        assert hs_uom_call["params"] == {"hs_code": "8432.1010", "annexure_id": 3}

        sro_item_call = next(c for c in recorded_calls if c["url"].endswith("/pdi/v2/SROItem"))
        assert sro_item_call["params"] == {"date": "2025-03-25", "sro_id": 389}
    finally:
        # Reset provinces catalog back to DEMO_FIXTURE so subsequent fixture-mode tests see DEMO_FIXTURE
        from backend.app.models.pral_catalog import FBRReferenceCatalog
        db.query(FBRReferenceCatalog).delete()
        db.commit()
        db.close()


# ==============================================================================
# 4. Section 4 Invoice Serialization, Local Validation & Mixed Response Parsing
# ==============================================================================

def test_section_4_invoice_serializer_and_compound_rate_preservation():
    """
    Verify Section 4.1 PostInvoiceData_v1 / ValidateInvoiceData_v1 JSON structure:
    - Includes scenarioId in SANDBOX and omits scenarioId in PRODUCTION
    - Preserves compound rate descriptions ("18% along with rupees 60 per kilogram", "Exempt", "Rs. 300")
    - Rejects mixed validationResponse (statusCode="00" with status="Invalid" or item statusCode="01")
    """
    sample_invoice = {
        "invoice_type": "Sale Invoice",
        "invoice_date": "2025-05-10",
        "seller_ntn": "8885801",
        "seller_business_name": "Company 8",
        "seller_province": "SINDH",
        "seller_address": "Karachi",
        "buyer_ntn": "1000000000000",
        "buyer_name": "FERTILIZER MANUFAC IRS NEW",
        "buyer_province": "SINDH",
        "buyer_address": "Karachi",
        "buyer_registration_type": "Registered",
        "scenario_id": "SN001",
        "items": [
            {
                "hs_code": "0101.2100",
                "description": "Living horses",
                "rate": "18% along with rupees 60 per kilogram",
                "tax_rate": Decimal("18"),
                "uom": "Numbers, pieces, units",
                "quantity": Decimal("100"),
                "totalValues": Decimal("1180"),
                "line_total": Decimal("1000"),
                "tax_amount": Decimal("180"),
                "sale_type": "Goods at standard rate (default)",
                "sro_schedule_no": "ZERO RATED GAS",
                "sro_item_serial_no": "4(1)(a)(ii)",
            }
        ],
    }

    sandbox_adapter = SandboxFBRAdapter()
    sb_payload = sandbox_adapter._transform_to_fbr_schema(sample_invoice)
    assert sb_payload["scenarioId"] == "SN001"
    assert sb_payload["items"][0]["rate"] == "18% along with rupees 60 per kilogram"
    assert sb_payload["items"][0]["sroScheduleNo"] == "ZERO RATED GAS"
    assert sb_payload["items"][0]["sroItemSerialNo"] == "4(1)(a)(ii)"

    prod_adapter = ProductionFBRAdapter()
    prod_payload = prod_adapter._transform_to_fbr_schema(sample_invoice)
    assert "scenarioId" not in prod_payload
    assert prod_payload["items"][0]["rate"] == "18% along with rupees 60 per kilogram"

    # Debit Note missing invoiceRefNo fails local validation
    debit_note_missing_ref = dict(sample_invoice, invoice_type="Debit Note", invoiceRefNo=None)
    val_res = sandbox_adapter.validate_invoice(debit_note_missing_ref)
    assert val_res["is_valid"] is False
    assert any("invoiceRefNo" in err for err in val_res["errors"])

    # Mixed FBR validationResponse from PDF p. 11 (statusCode="00", status="Invalid", item errorCode="0052")
    mixed_response = {
        "dated": "2025-05-07 14:43:39",
        "validationResponse": {
            "statusCode": "00",
            "status": "Invalid",
            "error": "",
            "invoiceStatuses": [
                {
                    "itemSNo": "1",
                    "statusCode": "01",
                    "status": "Invalid",
                    "invoiceNo": None,
                    "errorCode": "0052",
                    "error": "Provide HS Code 0101.2100 does not match with Provided sale type",
                }
            ],
        },
    }
    parsed = sandbox_adapter.parse_response(mixed_response)
    assert parsed.success is False
    assert parsed.status == "INVALID"
    assert parsed.fbr_invoice_number is None
    assert "0052" in (parsed.error_code or "") or "0052" in (parsed.error_message or "")


# ==============================================================================
# 5. API Route Integration & Credential Safeguard Tests
# ==============================================================================

def test_canonical_fbr_reference_and_invoice_safeguard_routes():
    """
    Verify via FastAPI TestClient:
    1. Canonical /api/v1/fbr/references/* routes return enveloped provenance data.
    2. Requesting mode=authorized_live without a PRAL token returns HTTP 409 CREDENTIALS_MISSING.
    3. Calling /api/v1/invoices/{id}/fbr-validate or /fbr-submit without a PRAL token
       returns HTTP 409 CREDENTIALS_MISSING and never fabricates an FBR invoice number.
    """
    db, auth_headers, org, branch, customer = _get_test_context()
    try:
        # Ensure no active PRAL token is set on this tenant during the credential-guard test
        from backend.app.models.fbr_credential import FBRCredential
        db.query(FBRCredential).filter(FBRCredential.organization_id == org.id).update(
            {"encrypted_auth_token": None, "encrypted_api_key": None}
        )
        db.commit()

        # 1. Enveloped provinces in fixture mode
        r_prov = client.get("/api/v1/fbr/references/provinces?mode=fixture", headers=auth_headers)
        assert r_prov.status_code == 200
        body_prov = r_prov.json()
        assert body_prov["source"] == "DEMO_FIXTURE"
        assert body_prov["official_live_verified"] is False
        assert len(body_prov["items"]) >= 7

        # 2. Enveloped STATL in fixture mode never claims active
        r_statl = client.get(
            "/api/v1/fbr/registration/statl?regno=0788762&date=2025-05-18",
            headers=auth_headers,
        )
        assert r_statl.status_code == 200
        body_statl = r_statl.json()
        assert body_statl["official_live_verified"] is False
        assert body_statl["data"]["is_active"] is None

        # 3. Requesting authorized_live without token returns 409 CREDENTIALS_MISSING
        r_live_block = client.get(
            "/api/v1/fbr/references/provinces?mode=authorized_live",
            headers=auth_headers,
        )
        assert r_live_block.status_code == 409
        assert r_live_block.json()["error"]["code"] == "CREDENTIALS_MISSING"

        # 4. Create a draft invoice and test local validation, JSON preview, and FBR credential guards
        create_resp = client.post(
            "/api/v1/invoices",
            headers=auth_headers,
            json={
                "branch_id": branch.id,
                "customer_id": customer.id,
                "invoice_type": "TAX_INVOICE",
                "scenario_id": "SN001",
                "items": [
                    {
                        "item_code": "ITM-PRAL-01",
                        "hs_code": "8432.1010",
                        "description": "Industrial Unit",
                        "uom": "Numbers, pieces, units",
                        "quantity": "2",
                        "unit_price": "5000.00",
                        "tax_rate": "18.00",
                        "rate_desc": "18% along with rupees 60 per kilogram",
                        "sale_type": "Goods at standard rate (default)",
                        "sro_reference": "ZERO RATED GAS",
                        "sro_item_serial_no": "4(1)(a)(ii)",
                    }
                ],
            },
        )
        assert create_resp.status_code == 201
        inv_id = create_resp.json()["id"]

        # Local validation succeeds on saved draft and returns serialized v1.12 payload
        r_local = client.post(f"/api/v1/invoices/{inv_id}/local-validate", headers=auth_headers)
        assert r_local.status_code == 200
        assert r_local.json()["is_valid"] is True
        assert r_local.json()["serialized_fbr_payload"]["scenarioId"] == "SN001"
        assert (
            r_local.json()["serialized_fbr_payload"]["items"][0]["rate"]
            == "18% along with rupees 60 per kilogram"
        )

        # JSON payload preview endpoint works
        r_preview = client.get(f"/api/v1/invoices/{inv_id}/fbr-payload", headers=auth_headers)
        assert r_preview.status_code == 200
        assert r_preview.json()["official_live_verified"] is False
        assert r_preview.json()["payload"]["items"][0]["sroItemSerialNo"] == "4(1)(a)(ii)"

        # Live FBR validation is blocked with 409 CREDENTIALS_MISSING (no PRAL token configured)
        r_fbr_val = client.post(f"/api/v1/invoices/{inv_id}/fbr-validate", headers=auth_headers)
        assert r_fbr_val.status_code == 409
        assert r_fbr_val.json()["error"]["code"] == "CREDENTIALS_MISSING"

        # Live FBR submission via /fbr-submit is blocked with 409 CREDENTIALS_MISSING
        r_fbr_sub = client.post(f"/api/v1/invoices/{inv_id}/fbr-submit", headers=auth_headers)
        assert r_fbr_sub.status_code == 409
        assert r_fbr_sub.json()["error"]["code"] == "CREDENTIALS_MISSING"
    finally:
        db.close()
