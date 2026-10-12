import pytest
from decimal import Decimal
from backend.app.services.tax_engine import PakistanTaxEngine, TaxCalculationError


def test_line_item_calculation_standard_rate():
    # 2 units @ PKR 45,000 with 18% sales tax
    calc = PakistanTaxEngine.calculate_line_item(
        quantity=Decimal("2"),
        unit_price=Decimal("45000.00"),
        discount=Decimal("0.00"),
        tax_rate_percent=Decimal("18.00")
    )
    assert calc["gross_amount"] == Decimal("90000.00")
    assert calc["taxable_amount"] == Decimal("90000.00")
    assert calc["tax_amount"] == Decimal("16200.00")
    assert calc["line_total"] == Decimal("106200.00")


def test_line_item_calculation_with_discount():
    # 2 units @ PKR 45,000 with PKR 2,000 discount and 18% sales tax
    calc = PakistanTaxEngine.calculate_line_item(
        quantity=Decimal("2"),
        unit_price=Decimal("45000.00"),
        discount=Decimal("2000.00"),
        tax_rate_percent=Decimal("18.00")
    )
    assert calc["gross_amount"] == Decimal("90000.00")
    assert calc["taxable_amount"] == Decimal("88000.00")
    assert calc["tax_amount"] == Decimal("15840.00")
    assert calc["line_total"] == Decimal("103840.00")


def test_discount_exceeding_gross_raises_error():
    with pytest.raises(TaxCalculationError):
        PakistanTaxEngine.calculate_line_item(
            quantity=Decimal("1"),
            unit_price=Decimal("100.00"),
            discount=Decimal("150.00")
        )


def test_invoice_totals_multi_item():
    items = [
        {"quantity": Decimal("2"), "unit_price": Decimal("45000.00"), "discount": Decimal("2000.00"), "tax_rate": Decimal("18.00")},
        {"quantity": Decimal("4"), "unit_price": Decimal("3500.00"), "discount": Decimal("0.00"), "tax_rate": Decimal("18.00")}
    ]
    totals = PakistanTaxEngine.calculate_invoice_totals(items, other_charges=Decimal("500.00"))
    
    # Line 1: Taxable 88,000, Tax 15,840
    # Line 2: Gross 14,000, Taxable 14,000, Tax 2,520
    # Subtotal: 104,000, Discount: 2,000, Taxable: 102,000, Tax: 18,360, Other: 500, Grand Total: 120,860
    assert totals["subtotal"] == Decimal("104000.00")
    assert totals["total_discount"] == Decimal("2000.00")
    assert totals["taxable_amount"] == Decimal("102000.00")
    assert totals["total_tax"] == Decimal("18360.00")
    assert totals["other_charges"] == Decimal("500.00")
    assert totals["grand_total"] == Decimal("120860.00")


if __name__ == "__main__":
    test_line_item_calculation_standard_rate()
    test_line_item_calculation_with_discount()
    test_invoice_totals_multi_item()
    print("All tax engine tests passed!")
