"""A failed Sandbox request must preserve the actual gateway outcome, not invent HTTP 400."""
from unittest.mock import patch

import httpx
import pytest

from backend.app.adapters.base import FBRAdapterResponse
from backend.app.adapters.sandbox_adapter import SandboxFBRAdapter, _safe_gateway_error
from backend.app.services.fbr_service import FBRService


class DummyResponse:
    def __init__(self, code, payload=None, text=""):
        self.status_code = code
        self.payload = payload
        self.text = text

    def json(self):
        if self.payload is None:
            raise ValueError("non-JSON gateway response")
        return self.payload


class DummyClient:
    def __init__(self, outcome=None, **kwargs):
        self.outcome = outcome

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, **kwargs):
        assert url == "https://gw.fbr.gov.pk/di_data/v1/di/postinvoicedata_sb"
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def submit_with(outcome):
    adapter = SandboxFBRAdapter(base_url="https://gw.fbr.gov.pk", bearer_token="test-private-token")
    adapter.validate_invoice = lambda invoice: {
        "is_valid": True,
        "transformed_payload": {"invoiceType": "Sale Invoice", "items": []},
    }
    with patch(
        "backend.app.adapters.sandbox_adapter.httpx.Client",
        side_effect=lambda **kwargs: DummyClient(outcome=outcome, **kwargs),
    ):
        return adapter.submit_invoice({})


def test_http_400_fbr_error_is_not_misreported_as_network_failure():
    gateway = DummyResponse(400, {
        "validationResponse": {
            "statusCode": "01",
            "status": "Invalid",
            "error": "Seller NTN is not registered in sandbox",
            "invoiceStatuses": [{"itemSeq": 1, "errorCode": "FBR100", "error": "Invalid HS code"}],
        }
    })
    response = submit_with(gateway)
    assert response.success is False
    assert response.status == "INVALID"
    assert response.error_code == "FBR-SBX-HTTP-400"
    assert "Seller NTN is not registered" in response.error_message
    assert "Invalid HS code" in response.error_message
    assert response.is_retryable is False
    assert response.raw_response["http_status"] == 400
    assert FBRService._observed_http_status(response) == 400


@pytest.mark.parametrize("status, retryable", [
    (401, False), (403, False), (422, False), (429, True), (500, True), (503, True)
])
def test_real_http_failure_codes_have_correct_retry_policy(status, retryable):
    result = submit_with(DummyResponse(status, {"error": "Gateway rejected request"}))
    assert result.success is False
    assert result.raw_response["http_status"] == status
    assert result.is_retryable is retryable
    assert result.error_code != "NET-SBX-UNEXPECTED"


def test_non_json_gateway_failure_reports_actual_http_status():
    result = submit_with(DummyResponse(400, text="<html><body>Proxy HTTP error</body></html>"))
    assert result.success is False
    assert result.raw_response["http_status"] == 400
    assert "HTTP 400" in result.error_message
    assert "html" not in result.error_message.lower()
    assert result.is_retryable is False


def test_http_200_invalid_payload_preserves_200_and_fbr_reason():
    result = submit_with(DummyResponse(200, {
        "validationResponse": {"statusCode": "01", "status": "Invalid", "error": "ScenarioId mismatch"}
    }))
    assert result.success is False
    assert "ScenarioId mismatch" in result.error_message
    assert FBRService._observed_http_status(result) == 200


def test_transport_exception_has_no_fabricated_http_400():
    result = submit_with(httpx.ConnectError("transport unavailable"))
    assert result.success is False
    assert result.error_code == "NET-SBX-CONN"
    assert FBRService._observed_http_status(result) is None


def test_unexpected_exception_is_not_retryable_and_reports_type_only():
    result = submit_with(RuntimeError("do not expose diagnostic sensitive detail"))
    assert result.success is False
    assert result.error_code == "NET-SBX-UNEXPECTED"
    assert result.is_retryable is False
    assert "RuntimeError" in result.error_message
    assert "sensitive detail" not in result.error_message
    assert FBRService._observed_http_status(result) is None


def test_gateway_error_redaction_and_local_failure_status():
    details = _safe_gateway_error({"message": "Bearer secretABC Authorization: privatePASSWORD"})
    assert "secretABC" not in details
    assert "privatePASSWORD" not in details
    local_failure = FBRAdapterResponse(success=False, status="INVALID", error_message="Local invalid HS code")
    assert FBRService._observed_http_status(local_failure) is None
