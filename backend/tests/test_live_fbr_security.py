"""Regression checks: live PRAL calls cannot be silently simulated."""
from unittest.mock import patch

import httpx

from backend.app.adapters.sandbox_adapter import SandboxFBRAdapter
from backend.app.services.fbr_verification_service import check_fbr_token


class FakeClient:
    def __init__(self, response=None, error=None, **kwargs):
        self.response = response
        self.error = error
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, **kwargs):
        assert url == "https://gw.fbr.gov.pk/pdi/v1/provinces"
        assert kwargs["headers"]["Authorization"] == "Bearer real-test-token"
        if self.error:
            raise self.error
        return self.response

    def post(self, url, **kwargs):
        assert url == "https://gw.fbr.gov.pk/di_data/v1/di/postinvoicedata_sb"
        if self.error:
            raise self.error
        return self.response


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload
        self.text = str(payload)

    def json(self):
        return self.payload


def test_official_reference_probe_never_verifies_missing_or_rejected_token():
    assert check_fbr_token("")["success"] is False
    with patch("backend.app.services.fbr_verification_service.httpx.Client",
               side_effect=lambda **kw: FakeClient(response=FakeResponse(401, {}), **kw)):
        result = check_fbr_token("real-test-token")
    assert result["success"] is False
    assert result["status"] == "AUTH_FAILED"


def test_official_reference_probe_verifies_valid_response_only():
    response = FakeResponse(200, [{"stateProvinceCode": 8, "stateProvinceDesc": "SINDH"}])
    with patch("backend.app.services.fbr_verification_service.httpx.Client",
               side_effect=lambda **kw: FakeClient(response=response, **kw)):
        result = check_fbr_token("real-test-token")
    assert result["success"] is True
    assert result["status"] == "VERIFIED"


def test_official_shared_host_sandbox_posts_real_not_simulated():
    response = FakeResponse(200, {
        "invoiceNumber": "PRAL-ACCEPT-123",
        "validationResponse": {
            "statusCode": "00",
            "status": "Valid",
            "invoiceStatuses": [],
        },
    })
    adapter = SandboxFBRAdapter(
        base_url="https://gw.fbr.gov.pk", bearer_token="real-test-token",
    )
    adapter.validate_invoice = lambda invoice: {
        "is_valid": True,
        "transformed_payload": {"invoiceType": "Sale Invoice", "items": []},
    }
    with patch("backend.app.adapters.sandbox_adapter.httpx.Client",
               side_effect=lambda **kw: FakeClient(response=response, **kw)):
        result = adapter.submit_invoice({})
    assert result.success is True
    assert result.fbr_invoice_number == "PRAL-ACCEPT-123"
    assert result.is_simulated is False


def test_official_shared_host_failure_never_generates_invoice_number():
    adapter = SandboxFBRAdapter(
        base_url="https://gw.fbr.gov.pk", bearer_token="real-test-token",
    )
    adapter.validate_invoice = lambda invoice: {
        "is_valid": True, "transformed_payload": {"items": []},
    }
    with patch("backend.app.adapters.sandbox_adapter.httpx.Client",
               side_effect=lambda **kw: FakeClient(error=httpx.ConnectError("offline"), **kw)):
        result = adapter.submit_invoice({})
    assert result.success is False
    assert result.fbr_invoice_number is None
    assert result.is_simulated is False
