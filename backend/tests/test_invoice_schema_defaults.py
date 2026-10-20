"""Regression tests for the uploaded invoice tax-rate schema changes."""
from decimal import Decimal

import pytest
from backend.app.schemas.invoice import InvoiceItemCreate


def _item(**overrides):
    values = {
        "item_code": "ITEM-001",
        "description": "Example taxable item",
        "hs_code": "8471.30.10",
        "quantity": Decimal("1"),
        "unit_price": Decimal("100"),
    }
    values.update(overrides)
    return InvoiceItemCreate(**values)


@pytest.mark.parametrize("value", [None, "", float("nan")])
def test_unset_tax_rate_defaults_to_eighteen_percent(value):
    assert _item(tax_rate=value).tax_rate == Decimal("18.00")


def test_missing_tax_rate_defaults_to_eighteen_percent():
    assert _item().tax_rate == Decimal("18.00")


@pytest.mark.parametrize("rate", ["0", "5", "15.5", Decimal("18.00")])
def test_valid_custom_tax_rate_is_preserved(rate):
    assert _item(tax_rate=rate).tax_rate == Decimal(str(rate))


def test_negative_tax_rate_is_rejected():
    with pytest.raises(ValueError):
        _item(tax_rate="-5")
