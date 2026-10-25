import pytest
from backend.app.adapters.sandbox_adapter import SandboxFBRAdapter
from backend.app.adapters.production_adapter import ProductionFBRAdapter

@pytest.mark.parametrize("adapter", [SandboxFBRAdapter, ProductionFBRAdapter])
@pytest.mark.parametrize("source,expected", [("18%%","18%"),("18%","18%"),("0%%","0%"),("0%","0%"),("5.5%%","5.5%"),("Exempt","Exempt"),("Rs. 200 per unit","Rs. 200 per unit")])
def test_numeric_percentage_description_is_not_double_suffixed(adapter,source,expected):
    assert adapter._format_fbr_rate(source)==expected
