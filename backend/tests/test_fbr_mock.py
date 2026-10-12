import pytest
from backend.app.adapters.mock_adapter import MockFBRAdapter


def test_mock_adapter_valid_submission():
    adapter = MockFBRAdapter()
    invoice_payload = {
        "invoice_number": "INV-KHI-01-2026-001001",
        "seller_ntn": "1234567-8",
        "seller_name": "ABC Distribution Pvt. Ltd.",
        "buyer_ntn": "9876543-2",
        "buyer_name": "XYZ Traders",
        "subtotal": 104000.00,
        "taxable_amount": 102000.00,
        "total_tax": 18360.00,
        "grand_total": 120360.00,
        "items": [
            {"hs_code": "8471.30.10", "quantity": 2, "tax_rate": 18.0}
        ]
    }

    res = adapter.submit_invoice(invoice_payload)
    assert res.success is True
    assert res.status == "VALID"
    assert res.fbr_invoice_number.startswith("FBR-")
    assert "FBR-DI|INV:" in res.qr_code_data
    assert res.error_code is None


def test_mock_adapter_simulated_timeout():
    adapter = MockFBRAdapter()
    invoice_payload = {
        "invoice_number": "INV-TIMEOUT-001",
        "seller_ntn": "1234567-8",
        "buyer_ntn": "9876543-2",
        "reference_number": "ERR-TIMEOUT-TEST",
        "items": [{"hs_code": "8471.30.10", "quantity": 1, "tax_rate": 18.0}]
    }

    res = adapter.submit_invoice(invoice_payload)
    assert res.success is False
    assert res.status == "FAILED"
    assert res.error_code == "NET-504"
    assert res.is_retryable is True


def test_mock_adapter_validation_error():
    adapter = MockFBRAdapter()
    invoice_payload = {
        "invoice_number": "INV-INVALID-001",
        "seller_ntn": "", # Missing NTN
        "items": [] # Missing items
    }

    res = adapter.submit_invoice(invoice_payload)
    assert res.success is False
    assert res.status == "INVALID"
    assert res.error_code == "FBR-VAL-100"
    assert res.is_retryable is False
