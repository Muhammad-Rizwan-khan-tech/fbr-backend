from backend.app.adapters.sandbox_adapter import SandboxFBRAdapter
from backend.app.adapters.production_adapter import ProductionFBRAdapter
from backend.app.adapters.integrator_adapter import LicensedIntegratorAdapter
from backend.app.adapters.factory import FBRAdapterFactory
from backend.app.adapters.mock_adapter import MockFBRAdapter


def test_sandbox_adapter_validation_and_submission():
    adapter = SandboxFBRAdapter(forced_scenario="VALID")
    assert adapter.environment == "SANDBOX"
    assert adapter.provider == "SANDBOX"
    assert adapter.is_simulated is False

    valid_payload = {
        "invoice_number": "INV-TEST-SBX-01",
        "seller_ntn": "1234567-8",
        "buyer_name": "Sandbox Buyer Corp",
        "buyer_ntn": "7654321-0",
        "subtotal": 1000.0,
        "taxable_amount": 1000.0,
        "total_tax": 180.0,
        "grand_total": 1180.0,
        "items": [
            {
                "item_code": "ITM-01",
                "description": "IT Consulting Services",
                "hs_code": "9983.11.00",
                "quantity": 1.0,
                "unit_price": 1000.0,
                "gross_amount": 1000.0,
                "taxable_amount": 1000.0,
                "tax_rate": 18.0,
                "tax_amount": 180.0,
                "line_total": 1180.0,
            }
        ],
    }

    # Test validation
    val_res = adapter.validate_invoice(valid_payload)
    assert val_res["is_valid"] is True

    # Test submission
    res = adapter.submit_invoice(valid_payload)
    assert res.success is True
    assert res.status == "VALID"
    assert res.fbr_invoice_number.startswith("SBX-")
    assert "FBR-DI-SBX" in res.qr_code_data
    assert res.environment == "SANDBOX"


def test_sandbox_adapter_test_connection():
    adapter = SandboxFBRAdapter()
    conn_result = adapter.test_connection()
    assert conn_result["success"] is True
    assert conn_result["status"] == "ONLINE"
    assert conn_result["environment"] == "SANDBOX"
    assert "latency_ms" in conn_result


def test_production_adapter_guard_unconfigured():
    adapter = ProductionFBRAdapter(bearer_token="", pos_id="")
    assert adapter.environment == "PRODUCTION"
    assert adapter.provider == "PRODUCTION"
    assert adapter.is_simulated is False
    assert adapter.is_configured() is False

    test_payload = {
        "invoice_number": "INV-PROD-01",
        "seller_ntn": "1234567-8",
        "grand_total": 5000.0,
    }

    # Should fail validation due to unconfigured live credentials
    val_res = adapter.validate_invoice(test_payload)
    assert val_res["is_valid"] is False
    assert any("FBR-PROD-CONFIG" in err for err in val_res["errors"])

    # Submission must reject immediately without faking success
    sub_res = adapter.submit_invoice(test_payload)
    assert sub_res.success is False
    assert sub_res.error_code in ("FBR-PROD-VAL-100", "FBR-PROD-UNCONFIGURED")


def test_production_adapter_test_connection_unconfigured():
    adapter = ProductionFBRAdapter(bearer_token="", pos_id="")
    conn = adapter.test_connection()
    assert conn["success"] is False
    assert conn["status"] == "UNCONFIGURED"
    assert "not configured" in conn["message"]


def test_licensed_integrator_adapter():
    adapter = LicensedIntegratorAdapter()
    assert adapter.environment == "PRODUCTION"
    assert adapter.provider == "LICENSED_INTEGRATOR"

    payload = {
        "invoice_number": "INV-INT-01",
        "seller_ntn": "1234567-8",
        "grand_total": 2500.0,
    }
    res = adapter.submit_invoice(payload)
    assert res.success is True
    assert res.fbr_invoice_number.startswith("INT-")
    assert "FBR-DI-INT" in res.qr_code_data


def test_adapter_factory_resolution():
    mock_ad = FBRAdapterFactory.get_adapter(mode="DEMO")
    assert isinstance(mock_ad, MockFBRAdapter)

    sbx_ad = FBRAdapterFactory.get_adapter(mode="SANDBOX")
    assert isinstance(sbx_ad, SandboxFBRAdapter)

    prod_ad = FBRAdapterFactory.get_adapter(mode="PRODUCTION")
    assert isinstance(prod_ad, ProductionFBRAdapter)

    int_ad = FBRAdapterFactory.get_adapter(mode="LICENSED_INTEGRATOR")
    assert isinstance(int_ad, LicensedIntegratorAdapter)


def test_di_v112_payload_mapping_no_legacy_keys():
    prod_adapter = ProductionFBRAdapter(bearer_token="dummy_token")
    sbx_adapter = SandboxFBRAdapter()

    invoice_data = {
        "invoice_type": "Sale Invoice",
        "invoice_date": "2025-02-18",
        "seller_ntn": "1234567-8",
        "seller_name": "ABC Enterprises",
        "seller_province": "Sindh",
        "seller_address": "Suite 101, Business Avenue, Karachi",
        "buyer_ntn": "9876543-2",
        "buyer_name": "XYZ Trading Ltd",
        "buyer_province": "Punjab",
        "buyer_address": "Plot 42, Industrial Area, Lahore",
        "buyer_registration_type": "Registered",
        "items": [
            {
                "item_code": "ITM-99",
                "hs_code": "8471.30.10",
                "description": "Laptop Computers Core i7",
                "tax_rate": 18.0,
                "rate": "18%",
                "uom": "Numbers",
                "quantity": 2.0,
                "unit_price": 150000.0,
                "gross_amount": 300000.0,
                "taxable_amount": 300000.0,
                "tax_amount": 54000.0,
                "line_total": 354000.0,
                "sale_type": "Goods at standard rate",
                "further_tax": 0.0,
                "extra_tax": 0.0,
            }
        ],
    }

    legacy_keys = [
        "InvoiceNumber", "POSID", "USIN", "DateTime",
        "BuyerNTN", "BuyerCNIC", "BuyerName",
        "TotalBillAmount", "TotalSaleValue", "TotalTaxCharged",
        "Items", "ItemCode", "PCTCode", "TaxRate",
        "SaleValue", "TotalAmount", "TaxCharged",
    ]

    for adapter in (prod_adapter, sbx_adapter):
        payload = adapter._transform_to_fbr_schema(invoice_data)

        # 1. Assert official DI API v1.12 required header fields
        expected_header_fields = [
            "invoiceType", "invoiceDate", "sellerNTNCNIC", "sellerBusinessName",
            "sellerProvince", "sellerAddress", "buyerNTNCNIC", "buyerBusinessName",
            "buyerProvince", "buyerAddress", "buyerRegistrationType", "items",
        ]
        for field in expected_header_fields:
            assert field in payload, f"Missing required header field {field} in {adapter.__class__.__name__}"

        # 2. Assert zero legacy keys in header
        for legacy_k in legacy_keys:
            assert legacy_k not in payload, f"Legacy key '{legacy_k}' found in header payload"

        # 3. Assert official DI API v1.12 required item fields
        assert len(payload["items"]) == 1
        item = payload["items"][0]
        expected_item_fields = [
            "hsCode", "productDescription", "rate", "uoM", "quantity",
            "totalValues", "valueSalesExcludingST", "fixedNotifiedValueOrRetailPrice",
            "salesTaxApplicable", "salesTaxWithheldAtSource", "saleType",
        ]
        for field in expected_item_fields:
            assert field in item, f"Missing required item field {field} in {adapter.__class__.__name__}"

        # 4. Assert zero legacy keys in items
        for legacy_k in legacy_keys:
            assert legacy_k not in item, f"Legacy key '{legacy_k}' found in item payload"

        # 5. Assert value types and formatting
        assert item["rate"] == "18%"
        assert item["uoM"] == "Numbers"
        assert item["saleType"] == "Goods at standard rate"
        assert isinstance(item["quantity"], (int, float))
        assert isinstance(item["totalValues"], (int, float))
        assert isinstance(item["valueSalesExcludingST"], (int, float))
        assert isinstance(item["salesTaxApplicable"], (int, float))
        assert isinstance(item["fixedNotifiedValueOrRetailPrice"], (int, float))
        assert isinstance(item["salesTaxWithheldAtSource"], (int, float))


def test_exact_production_and_sandbox_endpoints():
    prod = ProductionFBRAdapter(base_url="https://gw.fbr.gov.pk")
    assert prod.submit_url == "https://gw.fbr.gov.pk/di_data/v1/di/postinvoicedata"
    assert prod.validate_url == "https://gw.fbr.gov.pk/di_data/v1/di/validateinvoicedata"

    # Test stripping legacy path fragments
    prod_legacy = ProductionFBRAdapter(base_url="https://gw.fbr.gov.pk/api/v1/Invoice/PostData")
    assert prod_legacy.submit_url == "https://gw.fbr.gov.pk/di_data/v1/di/postinvoicedata"
    assert prod_legacy.validate_url == "https://gw.fbr.gov.pk/di_data/v1/di/validateinvoicedata"

    sbx = SandboxFBRAdapter(base_url="https://gw.fbr.gov.pk")
    assert sbx.submit_url == "https://gw.fbr.gov.pk/di_data/v1/di/postinvoicedata_sb"
    assert sbx.validate_url == "https://gw.fbr.gov.pk/di_data/v1/di/validateinvoicedata_sb"


def test_scenario_id_included_in_sandbox_and_omitted_in_production():
    test_data = {
        "invoice_number": "INV-SCEN-01",
        "seller_ntn": "1234567",
        "scenarioId": "SN001",
        "scenario_id": "SN001",
        "items": [
            {
                "hs_code": "9900.00.00",
                "description": "Item 1",
                "rate": "18%",
                "quantity": 1.0,
                "taxable_amount": 100.0,
                "tax_amount": 18.0,
            }
        ],
    }

    # Production MUST strictly omit scenarioId
    prod = ProductionFBRAdapter(bearer_token="dummy_prod_token")
    prod_payload = prod._transform_to_fbr_schema(test_data)
    assert "scenarioId" not in prod_payload

    # Sandbox MUST include valid scenarioId (^SN\d{3}$)
    sbx = SandboxFBRAdapter()
    sbx_payload = sbx._transform_to_fbr_schema(test_data)
    assert "scenarioId" in sbx_payload
    assert sbx_payload["scenarioId"] == "SN001"

    # Test invalid scenarioId validation in sandbox
    invalid_scen_data = dict(test_data, scenarioId="INVALID_FORMAT")
    val_res = sbx.validate_invoice(invalid_scen_data)
    assert val_res["is_valid"] is False
    assert any("scenarioId" in err for err in val_res["errors"])


def test_debit_note_invoice_ref_no_from_fbr_reference():
    # 1. Sale Invoice -> invoiceRefNo must be omitted
    sale_data = {
        "invoice_type": "Sale Invoice",
        "seller_ntn": "1234567",
        "reference_number": "FBR-ORIG-9999",
        "items": [{"hs_code": "9900.00.00", "description": "Item 1"}],
    }
    prod = ProductionFBRAdapter(bearer_token="dummy")
    sale_payload = prod._transform_to_fbr_schema(sale_data)
    assert "invoiceRefNo" not in sale_payload
    assert sale_payload["invoiceType"] == "Sale Invoice"

    # 2. Debit Note with reference -> invoiceRefNo must be populated
    debit_data = {
        "invoice_type": "Debit Note",
        "seller_ntn": "1234567",
        "reference_number": "FBR-ORIG-9999",
        "items": [{"hs_code": "9900.00.00", "description": "Item 1"}],
    }
    debit_payload = prod._transform_to_fbr_schema(debit_data)
    assert debit_payload["invoiceType"] == "Debit Note"
    assert debit_payload["invoiceRefNo"] == "FBR-ORIG-9999"

    # 3. Debit Note missing reference -> validate_invoice must reject
    missing_ref_data = {
        "invoice_type": "Debit Note",
        "seller_ntn": "1234567",
        "reference_number": "",
        "items": [{"hs_code": "9900.00.00", "description": "Item 1"}],
    }
    val_res = prod.validate_invoice(missing_ref_data)
    assert val_res["is_valid"] is False
    assert any("invoiceRefNo is required for Debit Note" in err for err in val_res["errors"])


def test_v112_response_parsing_success_and_failure():
    adapter = ProductionFBRAdapter(bearer_token="dummy")

    # 1. Success response
    success_raw = {
        "invoiceNumber": "FBR-DI-20250218-00129",
        "dated": "2025-02-18 12:30:00",
        "validationResponse": {
            "statusCode": "00",
            "status": "Valid",
            "error": None,
            "invoiceStatuses": [
                {"itemSeq": 1, "status": "Valid", "error": None}
            ],
        },
    }
    res_success = adapter.parse_response(success_raw)
    assert res_success.success is True
    assert res_success.status == "VALID"
    assert res_success.fbr_invoice_number == "FBR-DI-20250218-00129"
    assert "FBR-DI-20250218-00129" in res_success.qr_code_data

    # 2. HTTP 200 with validation failure
    fail_raw = {
        "invoiceNumber": None,
        "dated": "2025-02-18 12:30:00",
        "validationResponse": {
            "statusCode": "01",
            "status": "Invalid",
            "error": "Invalid Buyer NTN or registration inactive in FBR database",
            "invoiceStatuses": [],
        },
    }
    res_fail = adapter.parse_response(fail_raw)
    assert res_fail.success is False
    assert res_fail.status == "INVALID"
    assert res_fail.error_code == "FBR-DI-01"
    assert "Invalid Buyer NTN" in res_fail.error_message
    assert res_fail.fbr_invoice_number is None

    # 3. Item-level validation failure
    item_fail_raw = {
        "invoiceNumber": "FBR-DI-20250218-00130",
        "dated": "2025-02-18 12:30:00",
        "validationResponse": {
            "statusCode": "00",
            "status": "Valid",
            "error": None,
            "invoiceStatuses": [
                {"itemSeq": 1, "status": "Invalid", "error": "Invalid HS Code 9999.99.99"}
            ],
        },
    }
    res_item_fail = adapter.parse_response(item_fail_raw)
    assert res_item_fail.success is False
    assert res_item_fail.status == "INVALID"
    assert "Item 1: Invalid HS Code 9999.99.99" in res_item_fail.error_message

