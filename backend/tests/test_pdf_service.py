import datetime
from decimal import Decimal
from backend.app.models.invoice import Invoice, InvoiceItem
from backend.app.services.pdf_service import pdf_generator


def test_generate_invoice_pdf_success():
    invoice = Invoice(
        id="test-inv-pdf-1",
        tenant_id="tenant-alpha",
        branch_id="branch-1",
        customer_id="cust-1",
        invoice_number="INV-2026-TEST-001",
        invoice_date=datetime.datetime(2026, 10, 5, 12, 0, 0, tzinfo=datetime.timezone.utc),
        seller_name="Alpha Tech Pakistan",
        seller_ntn="1234567-8",
        seller_strn="3277876123456",
        seller_branch_code="01",
        seller_province="Sindh",
        buyer_name="Beta Retailers",
        buyer_ntn="9876543-2",
        buyer_registration_type="REGISTERED",
        buyer_address="123 Commercial St, Karachi",
        buyer_province="Sindh",
        subtotal=Decimal("50000.00"),
        total_discount=Decimal("2000.00"),
        taxable_amount=Decimal("48000.00"),
        total_tax=Decimal("8640.00"),
        other_charges=Decimal("0.00"),
        grand_total=Decimal("56640.00"),
        status="VALID",
        fbr_status="VALID",
        fbr_invoice_number="FBR-20261005-998877",
        fbr_environment="DEMO",
        fbr_provider="MOCK",
        fbr_is_simulated=True,
    )
    item = InvoiceItem(
        item_seq=1,
        item_code="HW-SERVER-01",
        description="High Performance Cloud Compute Node",
        hs_code="8471.49.00",
        quantity=Decimal("2.00"),
        uom="NOS",
        unit_price=Decimal("25000.00"),
        gross_amount=Decimal("50000.00"),
        discount=Decimal("2000.00"),
        taxable_amount=Decimal("48000.00"),
        tax_rate=Decimal("18.00"),
        tax_amount=Decimal("8640.00"),
        line_total=Decimal("56640.00"),
        sale_type="GOODS",
    )
    invoice.items = [item]

    pdf_bytes = pdf_generator.generate(invoice)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 2000
    assert pdf_bytes.startswith(b"%PDF")
    # Verify PDF contains binary structures and ReportLab metadata
    assert b"%%EOF" in pdf_bytes


def test_generate_invoice_pdf_production_mode():
    invoice = Invoice(
        id="test-inv-pdf-2",
        tenant_id="tenant-alpha",
        branch_id="branch-1",
        customer_id="cust-1",
        invoice_number="INV-2026-PROD-002",
        invoice_date=datetime.datetime(2026, 10, 5, 12, 0, 0, tzinfo=datetime.timezone.utc),
        seller_name="Alpha Tech Pakistan",
        seller_ntn="1234567-8",
        seller_strn="3277876123456",
        seller_branch_code="01",
        seller_province="Sindh",
        buyer_name="Beta Retailers",
        buyer_ntn="9876543-2",
        buyer_registration_type="REGISTERED",
        buyer_address="123 Commercial St, Karachi",
        buyer_province="Sindh",
        subtotal=Decimal("10000.00"),
        total_discount=Decimal("0.00"),
        taxable_amount=Decimal("10000.00"),
        total_tax=Decimal("1800.00"),
        other_charges=Decimal("0.00"),
        grand_total=Decimal("11800.00"),
        status="VALID",
        fbr_status="VALID",
        fbr_invoice_number="FBR-OFFICIAL-2026-0001",
        fbr_environment="PRODUCTION",
        fbr_provider="PRODUCTION",
        fbr_is_simulated=False,
    )
    invoice.items = []

    pdf_bytes = pdf_generator.generate(invoice)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")
