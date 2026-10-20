"""No-network regressions for real sandbox routing and credential verification."""
from unittest.mock import patch

from backend.app.adapters.sandbox_adapter import SandboxFBRAdapter
from backend.app.services.fbr_connection_service import probe_pral_reference


def test_reference_probe_never_verifies_missing_token():
    result = probe_pral_reference("", environment="SANDBOX")
    assert result["success"] is False
    assert result["status"] == "UNCONFIGURED"
    assert result["invoice_submission_verified"] is False


def test_reference_probe_checks_bearer_auth_without_submitting_invoice():
    class Resp:
        status_code = 200
        def json(self):
            return [{"stateProvinceCode": 7, "stateProvinceDesc": "PUNJAB"}]

    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, url, headers):
            assert url.endswith("/pdi/v1/provinces")
            assert headers["Authorization"] == "Bearer fake-token"
            return Resp()

    with patch("backend.app.services.fbr_connection_service.httpx.Client", Client):
        result = probe_pral_reference("fake-token")
    assert result["success"] is True
    assert result["authenticated_reference_access"] is True
    assert result["invoice_submission_verified"] is False


def test_sandbox_uses_real_sb_endpoint_on_gw_fbr_host():
    payload = {
        "invoice_number": "TEST-INV-01",
        "invoiceType": "Sale Invoice",
        "invoiceDate": "2026-10-21",
        "sellerNTNCNIC": "1234567",
        "sellerBusinessName": "Test Seller",
        "sellerProvince": "Sindh",
        "sellerAddress": "Hyderabad",
        "buyerNTNCNIC": "7654321",
        "buyerBusinessName": "Test Buyer",
        "buyerProvince": "Sindh",
        "buyerAddress": "Karachi",
        "buyerRegistrationType": "Registered",
        "scenarioId": "SN001",
        "items": [{
            "hsCode": "8471.30.10",
            "productDescription": "Laptop",
            "rate": "18%",
            "uoM": "Numbers, pieces, units",
            "quantity": 1,
            "valueSalesExcludingST": 1000.0,
            "salesTaxApplicable": 180.0,
            "totalValues": 1180.0,
            "saleType": "Goods at standard rate",
        }],
    }
    class Resp:
        status_code = 200
        def json(self):
            return {
                "invoiceNumber": "REAL-SANDBOX-REF",
                "validationResponse": {
                    "statusCode": "00",
                    "status": "Valid",
                    "invoiceStatuses": [],
                },
            }
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, json, headers):
            assert url == "https://gw.fbr.gov.pk/di_data/v1/di/postinvoicedata_sb"
            assert headers["Authorization"] == "Bearer fake-token"
            return Resp()
    with patch("backend.app.adapters.sandbox_adapter.httpx.Client", Client):
        result = SandboxFBRAdapter(
            bearer_token="fake-token", base_url="https://gw.fbr.gov.pk"
        ).submit_invoice(payload)
    assert result.success is True
    assert result.is_simulated is False
    assert result.fbr_invoice_number == "REAL-SANDBOX-REF"
