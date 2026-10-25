"""Official FBR DI v1.12 response and payload contract regression tests."""
import json
from unittest.mock import patch
import httpx
import pytest

from backend.app.adapters.gateway_response import inspect_gateway_response
from backend.app.adapters.sandbox_adapter import SandboxFBRAdapter
from backend.app.adapters.production_adapter import ProductionFBRAdapter


class FakeResponse:
    def __init__(self, body, status_code=200, content_type="application/json"):
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        self.payload = body
        self.text = body if isinstance(body, str) else json.dumps(body)

    def json(self):
        if self.headers["content-type"] == "text/html":
            raise ValueError("not JSON")
        return self.payload


class FakeClient:
    def __init__(self, response=None, **kwargs):
        self.response = response
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def post(self, url, **kwargs):
        assert url == "https://gw.fbr.gov.pk/di_data/v1/di/postinvoicedata_sb"
        assert kwargs["headers"]["Accept"] == "application/json"
        return self.response


def submit_response(response):
    adapter = SandboxFBRAdapter(
        base_url="https://gw.fbr.gov.pk/di_data/v1/di/postinvoicedata_sb",
        bearer_token="private-fixture-token",
    )
    adapter.validate_invoice = lambda _: {"is_valid": True, "transformed_payload": {"items": []}}
    with patch("backend.app.adapters.sandbox_adapter.httpx.Client",
               side_effect=lambda **kwargs: FakeClient(response=response, **kwargs)):
        result = adapter.submit_invoice({})
    return adapter, result


@pytest.mark.parametrize("body,media_type,kind", [
    ("<html>Gateway page</html>", "text/html", "html"),
    ("", "text/plain", "json_string"),
    ([], "application/json", "json_array"),
    ("Access denied", "application/json", "json_string"),
    (None, "application/json", "json_null"),
])
def test_http_200_non_invoice_content_is_never_marked_accepted(body, media_type, kind):
    _, result = submit_response(FakeResponse(body, content_type=media_type))
    assert result.success is False
    assert result.status == "FAILED"
    assert result.error_code == "FBR-SBX-RESPONSE-FORMAT"
    assert result.raw_response["response_kind"] == kind
    assert result.raw_response["http_status"] == 200
    assert result.raw_response["content_type"] == media_type
    assert "body_sha256_prefix" in result.raw_response
    assert result.fbr_invoice_number is None


def test_double_encoded_documented_invoice_response_can_be_read():
    actual = {
        "invoiceNumber": "7000007DI1747119701593",
        "validationResponse": {
            "statusCode": "00", "status": "Valid", "error": "",
            "invoiceStatuses": [{"itemSNo": 1, "status": "Valid", "statusCode": "00", "error": ""}],
        },
    }
    _, result = submit_response(FakeResponse(json.dumps(actual)))
    assert result.success is True
    assert result.status == "VALID"
    assert result.fbr_invoice_number == actual["invoiceNumber"]
    assert result.raw_response["response_kind"] == "wrapped_json_object"
    assert result.is_simulated is False


def test_list_with_valid_looking_invoice_is_not_accepted():
    body = [{
        "invoiceNumber": "looks-like-an-invoice",
        "validationResponse": {"statusCode": "00", "status": "Valid"},
    }]
    _, result = submit_response(FakeResponse(body))
    assert result.success is False
    assert result.fbr_invoice_number is None


def test_gateway_error_message_never_discloses_bearer_value():
    _, result = submit_response(FakeResponse("Bearer verysensitiveapikey HTTP error"))
    assert result.success is False
    assert "verysensitiveapikey" not in result.error_message
    assert "verysensitiveapikey" not in str(result.raw_response)


def test_real_gateway_payload_avoids_fabricated_buyer_id():
    adapter = SandboxFBRAdapter(base_url="https://gw.fbr.gov.pk", bearer_token="local-test")
    data = {
        "invoiceType": "Sale Invoice", "invoiceDate": "2026-10-24",
        "sellerNTNCNIC": "7654321", "sellerBusinessName": "Sample Seller",
        "sellerProvince": "Sindh", "sellerAddress": "Latifabad Hyderabad",
        "buyerNTNCNIC": "", "buyerBusinessName": "Counter Buyer",
        "buyerProvince": "Sindh", "buyerAddress": "Hyderabad",
        "buyerRegistrationType": "Unregistered", "scenarioId": "SN001",
        "items": [{
            "hsCode": "0101.2100", "productDescription": "Test product",
            "rate": "18%", "uoM": "NOS", "quantity": 1,
            "valueSalesExcludingST": 1000, "salesTaxApplicable": 180,
            "totalValues": 1180, "saleType": "STANDARD",
        }],
    }
    valid = adapter.validate_invoice(data)
    assert valid["is_valid"] is True, valid["errors"]
    payload = valid["transformed_payload"]
    assert payload["buyerNTNCNIC"] == ""
    assert payload["items"][0]["uoM"] == "Numbers, pieces, units"
    assert payload["items"][0]["saleType"] == "Goods at standard rate (default)"
    data["buyerRegistrationType"] = "Registered"
    assert adapter.validate_invoice(data)["is_valid"] is False


def test_normalized_full_endpoint_selects_correct_validate_and_submit_paths():
    adapter = SandboxFBRAdapter(
        base_url="https://gw.fbr.gov.pk/di_data/v1/di/postinvoicedata_sb",
        bearer_token="private-test",
    )
    assert adapter.submit_url == "https://gw.fbr.gov.pk/di_data/v1/di/postinvoicedata_sb"
    assert adapter.validate_url == "https://gw.fbr.gov.pk/di_data/v1/di/validateinvoicedata_sb"


def test_inspect_response_records_only_metadata_for_html_and_json_array():
    html, metadata = inspect_gateway_response(FakeResponse(
        "<html>FBR-LOGIN password=secret123</html>", content_type="text/html"
    ))
    assert html is None
    assert metadata["response_kind"] == "html"
    assert "secret123" not in str(metadata)
    array, metadata = inspect_gateway_response(FakeResponse(["gateway down"]))
    assert array is None
    assert metadata["array_items"] == 1


def test_official_host_normalizes_reference_path_in_render_settings():
    adapter = SandboxFBRAdapter(
        base_url="https://gw.fbr.gov.pk/pdi/v1/provinces",
        bearer_token="fixture-token",
    )
    assert adapter.submit_url == "https://gw.fbr.gov.pk/di_data/v1/di/postinvoicedata_sb"
    assert adapter.validate_url == "https://gw.fbr.gov.pk/di_data/v1/di/validateinvoicedata_sb"


def test_untrusted_gateway_never_receives_sandbox_invoice():
    adapter = SandboxFBRAdapter(
        base_url="https://some-other-domain.example",
        bearer_token="fixture-token",
    )
    adapter.validate_invoice = lambda _: {
        "is_valid": True, "transformed_payload": {"items": []}
    }
    with patch("backend.app.adapters.sandbox_adapter.httpx.Client") as http:
        outcome = adapter.submit_invoice({})
    assert outcome.success is False
    assert outcome.error_code == "FBR-SBX-GATEWAY-CONFIG"
    assert outcome.is_simulated is False
    assert http.call_count == 0


@pytest.mark.parametrize("adapter_class", [SandboxFBRAdapter, ProductionFBRAdapter])
@pytest.mark.parametrize("optional", [{}, {"extraTax": None, "discount": ""}, {"extraTax": 0, "discount": 0}])
def test_zero_numeric_fields_are_always_serialized(adapter_class, optional):
    adapter = adapter_class(base_url="https://gw.fbr.gov.pk", bearer_token="fixture")
    payload = adapter._transform_to_fbr_schema({"items": [{"quantity": 3, "valueSalesExcludingST": 21000, "salesTaxApplicable": 3780, **optional}]})
    item = payload["items"][0]
    for key in ("extraTax", "furtherTax", "fedPayable", "discount"):
        assert item[key] == 0.0
        assert isinstance(item[key], (int, float))
    assert item["totalValues"] == 24780


def test_real_http_response_with_literal_control_character_is_an_invalid_invoice():
    body = '{"validationResponse":{"statusCode":"01","status":"Invalid","invoiceStatuses":[{"itemSNo":"1","status":"Invalid","errorCode":"0300","error":"Provided numeric value\nDiscount Value is not valid"}]}}'
    _, result = submit_response(httpx.Response(200, text=body, headers={"content-type": "application/json"}))
    assert not result.success
    assert result.error_code == "FBR-SBX-0300"
    assert result.status == "INVALID"
    assert result.fbr_invoice_number is None


def test_malformed_gateway_rejection_keeps_error_code_without_acceptance():
    body = '{"validationResponse":{"statusCode":"01","status":"Invalid","invoiceStatuses":[{"errorCode":"0300","error":"Provided numeric value "discount" is invalid"}]}}'
    _, result = submit_response(httpx.Response(200, text=body))
    assert result.error_code == "FBR-SBX-0300"
    assert result.status == "INVALID"
    assert not result.success


def test_malformed_valid_looking_body_cannot_be_recovered_as_acceptance():
    body = '{"invoiceNumber":"fake","validationResponse":{"statusCode":"00","status":"Valid","error":"bad\njson"}}'
    _, result = submit_response(httpx.Response(200, text=body))
    assert not result.success
    assert result.fbr_invoice_number is None

