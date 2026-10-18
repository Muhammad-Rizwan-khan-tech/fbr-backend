"""Official PRAL / FBR Digital Invoicing v1.12 Reference Data Service.
Sourced from Technical Specification for DI API — User Manual, Version 1.12:
  Section 5: Reference Data APIs (pp. 22–34)

Implements all 12 official endpoints with exact documented URL paths,
case-sensitive query/body parameters, date formatters, wire-exact parsers,
DB-backed caching (`FBRReferenceCatalog`), sync run auditing (`FBRReferenceSyncRun`),
and strict provider modes (`fixture`, `cached_official`, `authorized_live`).
"""

from datetime import datetime, timedelta, timezone, date as date_type
import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import httpx
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.crypto import decrypt_secret
from backend.app.core.errors import (
    CredentialsMissingError,
    InvalidRequestError,
    SchemaDriftError,
    StaleReferenceError,
    UnauthorizedError,
    UpstreamUnavailableError,
)
from backend.app.models.fbr_credential import FBRCredential
from backend.app.models.pral_catalog import FBRReferenceCatalog, FBRReferenceSyncRun
from backend.app.schemas.pral_reference import (
    CatalogDatasetStatus,
    DataSourceTag,
    ProviderMode,
    ReferenceEnvelope,
    ReferenceReadinessResponse,
    StatlTransportStrategy,
    WireDocTypeItem,
    WireGetRegTypeResponse,
    WireHsUomItem,
    WireItemDescCodeItem,
    WireProvinceItem,
    WireSaleTypeToRateItem,
    WireSroItemByScheduleItem,
    WireSroItemCodeItem,
    WireSroScheduleItem,
    WireStatlResponse,
    WireTransTypeCodeItem,
    WireUomItem,
)

logger = logging.getLogger(__name__)

DEFAULT_PRAL_BASE_URL = "https://gw.fbr.gov.pk"

MONTH_ABBR = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def parse_input_date(val: Optional[Union[str, date_type, datetime]]) -> date_type:
    """Parse an ISO date (`YYYY-MM-DD`), PRAL date (`DD-Mon-YYYY`), or `date` object."""
    if val is None:
        return datetime.now(timezone.utc).date()
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date_type):
        return val
    raw = str(val).strip()
    if not raw:
        return datetime.now(timezone.utc).date()
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%B-%Y", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise InvalidRequestError(f"Invalid date format '{raw}'. Expected YYYY-MM-DD or DD-Mon-YYYY.")


def format_pral_dd_mon_yyyy(val: Optional[Union[str, date_type, datetime]]) -> str:
    """Format date as `DD-Mon-YYYY` (e.g. `04-Feb-2024` or `24-Feb-2024`) for 5.7 and 5.8."""
    d = parse_input_date(val)
    return f"{d.day:02d}-{MONTH_ABBR[d.month - 1]}-{d.year:04d}"


def format_pral_iso_date(val: Optional[Union[str, date_type, datetime]]) -> str:
    """Format date as `YYYY-MM-DD` (e.g. `2025-03-25` or `2025-05-18`) for 5.10 and 5.11."""
    d = parse_input_date(val)
    return f"{d.year:04d}-{d.month:02d}-{d.day:02d}"


def build_request_fingerprint(catalog_key: str, params: Optional[Dict[str, Any]] = None) -> str:
    """Deterministic SHA-256 fingerprint for parameterized reference catalog caching."""
    if not params:
        return f"{catalog_key}:global"
    canonical = json.dumps(params, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]
    return f"{catalog_key}:{digest}"


# ---------------------------------------------------------------------------
# Clearly-Labeled DEMO_FIXTURE Datasets (Sourced from PRAL DI API v1.12 PDF)
# ---------------------------------------------------------------------------

# Section 5.1: GET /pdi/v1/provinces (PDF p. 22)
FALLBACK_PROVINCES = [
    {
        "id": 7, "code": "7", "label": "PUNJAB",
        "stateProvinceCode": 7, "stateProvinceDesc": "PUNJAB",
        "province_code": "01", "province_name": "Punjab", "sales_tax_authority": "PRA", "standard_rate": 16.0,
    },
    {
        "id": 8, "code": "8", "label": "SINDH",
        "stateProvinceCode": 8, "stateProvinceDesc": "SINDH",
        "province_code": "02", "province_name": "Sindh", "sales_tax_authority": "SRB", "standard_rate": 15.0,
    },
    {
        "id": 2, "code": "2", "label": "KHYBER PAKHTUNKHWA",
        "stateProvinceCode": 2, "stateProvinceDesc": "KHYBER PAKHTUNKHWA",
        "province_code": "03", "province_name": "Khyber Pakhtunkhwa", "sales_tax_authority": "KPRA", "standard_rate": 15.0,
    },
    {
        "id": 6, "code": "6", "label": "BALOCHISTAN",
        "stateProvinceCode": 6, "stateProvinceDesc": "BALOCHISTAN",
        "province_code": "04", "province_name": "Balochistan", "sales_tax_authority": "BRA", "standard_rate": 15.0,
    },
    {
        "id": 5, "code": "5", "label": "CAPITAL TERRITORY",
        "stateProvinceCode": 5, "stateProvinceDesc": "CAPITAL TERRITORY",
        "province_code": "05", "province_name": "Islamabad Capital Territory", "sales_tax_authority": "FBR", "standard_rate": 18.0,
    },
    {
        "id": 3, "code": "3", "label": "GILGIT BALTISTAN",
        "stateProvinceCode": 3, "stateProvinceDesc": "GILGIT BALTISTAN",
        "province_code": "06", "province_name": "Gilgit-Baltistan", "sales_tax_authority": "GBRA", "standard_rate": 0.0,
    },
    {
        "id": 4, "code": "4", "label": "AZAD JAMMU AND KASHMIR",
        "stateProvinceCode": 4, "stateProvinceDesc": "AZAD JAMMU AND KASHMIR",
        "province_code": "07", "province_name": "Azad Jammu & Kashmir", "sales_tax_authority": "AJK-CBR", "standard_rate": 18.0,
    },
]

# Section 5.2: GET /pdi/v1/doctypecode (PDF p. 23)
FALLBACK_DOC_TYPES = [
    {
        "id": 4, "code": "4", "label": "Sale Invoice",
        "docTypeId": 4, "docDescription": "Sale Invoice",
        "doc_type_code": "01", "doc_type_name": "Sale Invoice",
    },
    {
        "id": 9, "code": "9", "label": "Debit Note",
        "docTypeId": 9, "docDescription": "Debit Note",
        "doc_type_code": "02", "doc_type_name": "Debit Note",
    },
]

# Section 5.3: GET /pdi/v1/itemdesccode (PDF p. 24 + Section 10 samples)
FALLBACK_COMMON_HS_CODES = [
    {
        "id": "8432.1010", "code": "8432.1010",
        "label": "8432.1010 — NUCLEAR REACTORS, BOILERS, MACHINERY AND MECHANICAL APPLIANCES - PLOUGHS - CHISEL PLOUGHS",
        "hS_CODE": "8432.1010",
        "hs_code": "8432.1010",
        "description": "NUCLEAR REACTORS, BOILERS, MACHINERY AND MECHANICAL APPLIANCES; PARTS THEREOF. - AGRICULTURAL, HORTICULTURAL OR FORESTRY MACHINERY FOR SOIL PREPARATION OR CULTIVATION; LAWN OR SPORTS-GROUND ROLLERS. - PLOUGHS - CHISEL PLOUGHS",
        "default_uom": "Numbers, pieces, units",
        "allowed_uoms": ["Numbers, pieces, units", "KG"],
    },
    {
        "id": "5904.9000", "code": "5904.9000",
        "label": "5904.9000 — LINOLEUM, WHETHER OR NOT CUT TO SHAPE; FLOOR COVERINGS",
        "hS_CODE": "5904.9000",
        "hs_code": "5904.9000",
        "description": "LINOLEUM, WHETHER OR NOT CUT TO SHAPE; FLOOR COVERINGS CONSISTING OF A COATING OR COVERING APPLIED ON A TEXTILE BACKING",
        "default_uom": "Square Meter",
        "allowed_uoms": ["Square Meter", "Square Metre", "KG"],
    },
    {
        "id": "0101.2100", "code": "0101.2100",
        "label": "0101.2100 — Live horses, asses, mules and hinnies - Pure-bred breeding animals",
        "hS_CODE": "0101.2100",
        "hs_code": "0101.2100",
        "description": "Live horses, asses, mules and hinnies - Pure-bred breeding animals",
        "default_uom": "Numbers, pieces, units",
        "allowed_uoms": ["Numbers, pieces, units", "KG"],
    },
    {
        "id": "8471.30.10", "code": "8471.30.10",
        "label": "8471.30.10 — Laptops and portable digital automatic data processing machines",
        "hS_CODE": "8471.30.10",
        "hs_code": "8471.30.10",
        "description": "Laptops and portable digital automatic data processing machines",
        "default_uom": "Numbers, pieces, units",
        "allowed_uoms": ["Numbers, pieces, units", "NUM", "PCS", "BOX"],
    },
    {
        "id": "8517.13.00", "code": "8517.13.00",
        "label": "8517.13.00 — Smartphones and cellular devices",
        "hS_CODE": "8517.13.00",
        "hs_code": "8517.13.00",
        "description": "Smartphones and cellular devices",
        "default_uom": "Numbers, pieces, units",
        "allowed_uoms": ["Numbers, pieces, units", "NUM", "PCS", "BOX"],
    },
    {
        "id": "7318.15.00", "code": "7318.15.00",
        "label": "7318.15.00 — Screws, bolts, fasteners of iron or steel",
        "hS_CODE": "7318.15.00",
        "hs_code": "7318.15.00",
        "description": "Screws, bolts, fasteners of iron or steel",
        "default_uom": "KG",
        "allowed_uoms": ["KG", "KGS", "Numbers, pieces, units", "BOX"],
    },
    {
        "id": "4811.90.00", "code": "4811.90.00",
        "label": "4811.90.00 — Paper, paperboard, cellulose wadding",
        "hS_CODE": "4811.90.00",
        "hs_code": "4811.90.00",
        "description": "Paper, paperboard, cellulose wadding",
        "default_uom": "KG",
        "allowed_uoms": ["KG", "KGS", "BOX", "MT"],
    },
    {
        "id": "9983.11.00", "code": "9983.11.00",
        "label": "9983.11.00 — Information technology and software consultancy services",
        "hS_CODE": "9983.11.00",
        "hs_code": "9983.11.00",
        "description": "Information technology and software consultancy services",
        "default_uom": "Numbers, pieces, units",
        "allowed_uoms": ["Numbers, pieces, units", "Hours", "HRS", "NUM"],
    },
    {
        "id": "2710.12.10", "code": "2710.12.10",
        "label": "2710.12.10 — Motor spirit (petrol)",
        "hS_CODE": "2710.12.10",
        "hs_code": "2710.12.10",
        "description": "Motor spirit (petrol)",
        "default_uom": "Litre",
        "allowed_uoms": ["Litre", "LTR", "MT"],
    },
    {
        "id": "5201.00.90", "code": "5201.00.90",
        "label": "5201.00.90 — Raw cotton, not carded or combed",
        "hS_CODE": "5201.00.90",
        "hs_code": "5201.00.90",
        "description": "Raw cotton, not carded or combed",
        "default_uom": "KG",
        "allowed_uoms": ["KG", "KGS", "BAG", "MT"],
    },
    {
        "id": "1701.99.10", "code": "1701.99.10",
        "label": "1701.99.10 — Refined white cane sugar",
        "hS_CODE": "1701.99.10",
        "hs_code": "1701.99.10",
        "description": "Refined white cane sugar",
        "default_uom": "KG",
        "allowed_uoms": ["KG", "KGS", "BAG", "MT"],
    },
    {
        "id": "0902.40.10", "code": "0902.40.10",
        "label": "0902.40.10 — Black tea in bulk or retail packs",
        "hS_CODE": "0902.40.10",
        "hs_code": "0902.40.10",
        "description": "Black tea in bulk or retail packs",
        "default_uom": "KG",
        "allowed_uoms": ["KG", "KGS", "BOX", "BAG"],
    },
]

# Section 5.4: GET /pdi/v1/sroitemcode (PDF p. 25)
FALLBACK_SRO_ITEM_CODES = [
    {"id": 724, "code": "724", "label": "9", "srO_ITEM_ID": 724, "srO_ITEM_DESC": "9"},
    {"id": 725, "code": "725", "label": "1", "srO_ITEM_ID": 725, "srO_ITEM_DESC": "1"},
    {"id": 726, "code": "726", "label": "2", "srO_ITEM_ID": 726, "srO_ITEM_DESC": "2"},
    {"id": 17853, "code": "17853", "label": "50", "srO_ITEM_ID": 17853, "srO_ITEM_DESC": "50"},
    {
        "id": 17854, "code": "17854",
        "label": "Region/Area - (i) Gilgit-Baltistan (ii) Balochistan (outside quota) (iii) Azad Jammu and Kashmir",
        "srO_ITEM_ID": 17854,
        "srO_ITEM_DESC": "Region/Area - (i) Gilgit-Baltistan (ii) Balochistan (outside quota) (iii) Azad Jammu and Kashmir",
    },
]

# Section 5.5: GET /pdi/v1/transtypecode (PDF p. 26 & Section 10)
FALLBACK_TRANSACTION_TYPES = [
    {
        "id": 75, "code": "75", "label": "Goods at standard rate (default)",
        "transactioN_TYPE_ID": 75, "transactioN_DESC": "Goods at standard rate (default)",
        "trans_type_code": "01", "trans_type_name": "Goods at standard rate (default)",
    },
    {
        "id": 80, "code": "80", "label": "Goods at Reduced Rate",
        "transactioN_TYPE_ID": 80, "transactioN_DESC": "Goods at Reduced Rate",
        "trans_type_code": "02", "trans_type_name": "Goods at Reduced Rate",
    },
    {
        "id": 81, "code": "81", "label": "Exempt goods",
        "transactioN_TYPE_ID": 81, "transactioN_DESC": "Exempt goods",
        "trans_type_code": "03", "trans_type_name": "Exempt goods",
    },
    {
        "id": 82, "code": "82", "label": "DTRE goods",
        "transactioN_TYPE_ID": 82, "transactioN_DESC": "DTRE goods",
        "trans_type_code": "04", "trans_type_name": "DTRE goods",
    },
    {
        "id": 83, "code": "83", "label": "3rd Schedule Goods",
        "transactioN_TYPE_ID": 83, "transactioN_DESC": "3rd Schedule Goods",
        "trans_type_code": "05", "trans_type_name": "3rd Schedule Goods",
    },
    {
        "id": 84, "code": "84", "label": "Goods at zero-rate",
        "transactioN_TYPE_ID": 84, "transactioN_DESC": "Goods at zero-rate",
        "trans_type_code": "06", "trans_type_name": "Goods at zero-rate",
    },
    {
        "id": 85, "code": "85", "label": "Steel melting and re-rolling",
        "transactioN_TYPE_ID": 85, "transactioN_DESC": "Steel melting and re-rolling",
        "trans_type_code": "07", "trans_type_name": "Steel melting and re-rolling",
    },
    {
        "id": 86, "code": "86", "label": "Ship breaking",
        "transactioN_TYPE_ID": 86, "transactioN_DESC": "Ship breaking",
        "trans_type_code": "08", "trans_type_name": "Ship breaking",
    },
    {
        "id": 87, "code": "87", "label": "Spun yarn",
        "transactioN_TYPE_ID": 87, "transactioN_DESC": "Spun yarn",
        "trans_type_code": "09", "trans_type_name": "Spun yarn",
    },
    {
        "id": 111, "code": "111", "label": "Electricity Supply to Retailers",
        "transactioN_TYPE_ID": 111, "transactioN_DESC": "Electricity Supply to Retailers",
        "trans_type_code": "10", "trans_type_name": "Electricity Supply to Retailers",
    },
    {
        "id": 112, "code": "112", "label": "Services",
        "transactioN_TYPE_ID": 112, "transactioN_DESC": "Services",
        "trans_type_code": "11", "trans_type_name": "Services",
    },
    {
        "id": 115, "code": "115", "label": "Potassium Chlorate",
        "transactioN_TYPE_ID": 115, "transactioN_DESC": "Potassium Chlorate",
        "trans_type_code": "12", "trans_type_name": "Potassium Chlorate",
    },
    {
        "id": 120, "code": "120", "label": "Petroleum Products",
        "transactioN_TYPE_ID": 120, "transactioN_DESC": "Petroleum Products",
        "trans_type_code": "13", "trans_type_name": "Petroleum Products",
    },
    {
        "id": 125, "code": "125", "label": "CNG Sales",
        "transactioN_TYPE_ID": 125, "transactioN_DESC": "CNG Sales",
        "trans_type_code": "14", "trans_type_name": "CNG Sales",
    },
    {
        "id": 130, "code": "130", "label": "Toll Manufacturing",
        "transactioN_TYPE_ID": 130, "transactioN_DESC": "Toll Manufacturing",
        "trans_type_code": "15", "trans_type_name": "Toll Manufacturing",
    },
]

# Section 5.6: GET /pdi/v1/uom (PDF p. 27)
FALLBACK_UOMS = [
    {"id": 77, "code": "77", "label": "Square Metre", "uoM_ID": 77, "description": "Square Metre", "uom_code": "SQM", "uom_name": "Square Metre", "symbol": "m2"},
    {"id": 13, "code": "13", "label": "KG", "uoM_ID": 13, "description": "KG", "uom_code": "KGS", "uom_name": "Kilograms", "symbol": "kg"},
    {"id": 1, "code": "1", "label": "Numbers, pieces, units", "uoM_ID": 1, "description": "Numbers, pieces, units", "uom_code": "NUM", "uom_name": "Numbers", "symbol": "Nos"},
    {"id": 2, "code": "2", "label": "Litre", "uoM_ID": 2, "description": "Litre", "uom_code": "LTR", "uom_name": "Liters", "symbol": "L"},
    {"id": 3, "code": "3", "label": "Metre", "uoM_ID": 3, "description": "Metre", "uom_code": "MTR", "uom_name": "Meters", "symbol": "m"},
    {"id": 4, "code": "4", "label": "MT", "uoM_ID": 4, "description": "MT", "uom_code": "TON", "uom_name": "Metric Tons", "symbol": "ton"},
    {"id": 5, "code": "5", "label": "Boxes", "uoM_ID": 5, "description": "Boxes", "uom_code": "BOX", "uom_name": "Boxes", "symbol": "box"},
    {"id": 6, "code": "6", "label": "Bags", "uoM_ID": 6, "description": "Bags", "uom_code": "BAG", "uom_name": "Bags", "symbol": "bag"},
    {"id": 7, "code": "7", "label": "Hours", "uoM_ID": 7, "description": "Hours", "uom_code": "HRS", "uom_name": "Hours", "symbol": "hrs"},
    {"id": 8, "code": "8", "label": "MMBTU", "uoM_ID": 8, "description": "MMBTU", "uom_code": "MMBTU", "uom_name": "MMBTU", "symbol": "MMBTU"},
    {"id": 9, "code": "9", "label": "KWH", "uoM_ID": 9, "description": "KWH", "uom_code": "KWH", "uom_name": "KWH", "symbol": "kWh"},
]

# Section 5.7: GET /pdi/v1/SroSchedule (PDF p. 28)
FALLBACK_SRO_SCHEDULES = [
    {"id": 7, "code": "7", "label": "Zero Rated Gas", "srO_ID": 7, "srO_DESC": "Zero Rated Gas"},
    {"id": 8, "code": "8", "label": "5th Schedule", "srO_ID": 8, "srO_DESC": "5th Schedule"},
    {"id": 6, "code": "6", "label": "Sixth Schedule Table I", "srO_ID": 6, "srO_DESC": "Sixth Schedule Table I"},
    {"id": 9, "code": "9", "label": "Eighth Schedule Table 1", "srO_ID": 9, "srO_DESC": "Eighth Schedule Table 1"},
    {"id": 389, "code": "389", "label": "SRO 389(I)/2025", "srO_ID": 389, "srO_DESC": "SRO 389(I)/2025"},
    {"id": 1450, "code": "1450", "label": "1450(I)/2021", "srO_ID": 1450, "srO_DESC": "1450(I)/2021"},
    {"id": 297, "code": "297", "label": "SRO 297(I)/2023-Table-I", "srO_ID": 297, "srO_DESC": "SRO 297(I)/2023-Table-I"},
]

# Section 5.8: GET /pdi/v2/SaleTypeToRate (PDF p. 29)
FALLBACK_SALE_TYPE_RATES: Dict[int, List[Dict[str, Any]]] = {
    75: [
        {"id": 701, "code": "701", "label": "18%", "rate_value": 18.0, "ratE_ID": 701, "ratE_DESC": "18%", "ratE_VALUE": 18.0},
    ],
    80: [
        {"id": 710, "code": "710", "label": "1%", "rate_value": 1.0, "ratE_ID": 710, "ratE_DESC": "1%", "ratE_VALUE": 1.0},
        {"id": 711, "code": "711", "label": "5%", "rate_value": 5.0, "ratE_ID": 711, "ratE_DESC": "5%", "ratE_VALUE": 5.0},
        {"id": 712, "code": "712", "label": "10%", "rate_value": 10.0, "ratE_ID": 712, "ratE_DESC": "10%", "ratE_VALUE": 10.0},
    ],
    81: [
        {"id": 720, "code": "720", "label": "Exempt", "rate_value": 0.0, "ratE_ID": 720, "ratE_DESC": "Exempt", "ratE_VALUE": 0.0},
    ],
    82: [
        {"id": 721, "code": "721", "label": "0%", "rate_value": 0.0, "ratE_ID": 721, "ratE_DESC": "0%", "ratE_VALUE": 0.0},
    ],
    83: [
        {"id": 701, "code": "701", "label": "18%", "rate_value": 18.0, "ratE_ID": 701, "ratE_DESC": "18%", "ratE_VALUE": 18.0},
    ],
    84: [
        {"id": 721, "code": "721", "label": "0%", "rate_value": 0.0, "ratE_ID": 721, "ratE_DESC": "0%", "ratE_VALUE": 0.0},
    ],
    112: [
        {"id": 730, "code": "730", "label": "15%", "rate_value": 15.0, "ratE_ID": 730, "ratE_DESC": "15%", "ratE_VALUE": 15.0},
        {"id": 731, "code": "731", "label": "16%", "rate_value": 16.0, "ratE_ID": 731, "ratE_DESC": "16%", "ratE_VALUE": 16.0},
    ],
    115: [
        {
            "id": 734, "code": "734",
            "label": "18% along with rupees 60 per kilogram",
            "rate_value": 18.0,
            "ratE_ID": 734,
            "ratE_DESC": "18% along with rupees 60 per kilogram",
            "ratE_VALUE": 18.0,
        },
    ],
}

CATALOG_METADATA = [
    ("provinces", "5.1", "/pdi/v1/provinces", 86400 * 7),
    ("doctypecode", "5.2", "/pdi/v1/doctypecode", 86400 * 7),
    ("itemdesccode", "5.3", "/pdi/v1/itemdesccode", 86400),
    ("sroitemcode", "5.4", "/pdi/v1/sroitemcode", 86400),
    ("transtypecode", "5.5", "/pdi/v1/transtypecode", 86400),
    ("uom", "5.6", "/pdi/v1/uom", 86400 * 7),
    ("sro_schedule", "5.7", "/pdi/v1/SroSchedule", 43200),
    ("sale_type_to_rate", "5.8", "/pdi/v2/SaleTypeToRate", 43200),
    ("hs_uom", "5.9", "/pdi/v2/HS_UOM", 86400),
    ("sro_item", "5.10", "/pdi/v2/SROItem", 43200),
    ("statl", "5.11", "/dist/v1/statl", 3600),
    ("get_reg_type", "5.12", "/dist/v1/Get_Reg_Type", 3600),
]


class PralReferenceService:
    """Manages fetching, validating, DB-caching, and querying all 12 PRAL v1.12 reference APIs."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
        statl_transport_strategy: StatlTransportStrategy = StatlTransportStrategy.QUERY_PARAMS,
    ):
        self.base_url = (base_url or settings.FBR_API_URL or DEFAULT_PRAL_BASE_URL).rstrip("/")
        # Strip any accidental path suffixes so self.base_url is purely scheme://host[:port]
        for suffix in ("/di_data", "/pdi", "/dist", "/api"):
            if suffix in self.base_url:
                self.base_url = self.base_url.split(suffix)[0].rstrip("/")
        self.bearer_token = (bearer_token if bearer_token is not None else (settings.FBR_API_KEY or "")).strip()
        self.statl_transport_strategy = statl_transport_strategy
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl_seconds = 86400  # 24 Hours

    def resolve_token(self, db: Optional[Session] = None, tenant_id: Optional[str] = None) -> str:
        """Resolve PRAL Bearer token from tenant FBRCredential vault or global settings.
        Never exposes the raw token outside the backend adapter call.
        """
        if db is not None and tenant_id:
            cred = (
                db.query(FBRCredential)
                .filter(
                    FBRCredential.organization_id == tenant_id,
                    FBRCredential.is_active == True,  # noqa: E712
                )
                .first()
            )
            if cred:
                for enc_field in (cred.encrypted_auth_token, cred.encrypted_api_key):
                    if enc_field:
                        try:
                            dec = decrypt_secret(enc_field)
                            if dec and dec.strip():
                                return dec.strip()
                        except Exception:
                            continue
        return self.bearer_token

    def has_token(self, db: Optional[Session] = None, tenant_id: Optional[str] = None) -> bool:
        return bool(self.resolve_token(db=db, tenant_id=tenant_id))

    def _get_headers(self, token: Optional[str] = None) -> Dict[str, str]:
        resolved = (token if token is not None else self.bearer_token).strip()
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "FBR-Invoice-Cloud/1.12",
        }
        if resolved:
            headers["Authorization"] = f"Bearer {resolved}"
        return headers

    def _record_sync_run(
        self,
        db: Optional[Session],
        *,
        tenant_id: Optional[str],
        catalog_key: str,
        request_fingerprint: str,
        provider_mode: str,
        outcome: str,
        record_count: int = 0,
        error_code: Optional[str] = None,
        error_summary: Optional[str] = None,
        triggered_by: str = "system",
    ) -> None:
        if db is None:
            return
        try:
            now = datetime.now(timezone.utc)
            run = FBRReferenceSyncRun(
                tenant_id=tenant_id,
                catalog_key=catalog_key,
                request_fingerprint=request_fingerprint,
                provider_mode=provider_mode,
                started_at=now,
                finished_at=now,
                outcome=outcome,
                record_count=record_count,
                error_code=error_code,
                error_summary=error_summary,
                triggered_by=triggered_by,
            )
            db.add(run)
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning("Failed to record FBRReferenceSyncRun: %s", exc)

    def _upsert_db_catalog(
        self,
        db: Optional[Session],
        *,
        tenant_id: Optional[str],
        catalog_key: str,
        request_fingerprint: str,
        source: str,
        payload_data: Any,
        record_count: int,
        effective_date: Optional[str],
        ttl_seconds: int,
        official_live_verified: bool,
        last_error: Optional[str] = None,
    ) -> Optional[FBRReferenceCatalog]:
        if db is None:
            return None
        try:
            now = datetime.now(timezone.utc)
            expires = now + timedelta(seconds=ttl_seconds)
            existing = (
                db.query(FBRReferenceCatalog)
                .filter(
                    FBRReferenceCatalog.tenant_id == tenant_id,
                    FBRReferenceCatalog.catalog_key == catalog_key,
                    FBRReferenceCatalog.request_fingerprint == request_fingerprint,
                )
                .first()
            )
            serialized = json.dumps(payload_data, default=str)
            if existing:
                existing.source = source
                existing.source_version = "1.12"
                existing.payload = serialized
                existing.record_count = record_count
                existing.fetched_at = now
                existing.effective_date = effective_date
                existing.expires_at = expires
                existing.status = "ACTIVE"
                existing.official_live_verified = official_live_verified
                existing.last_error = last_error
                row = existing
            else:
                row = FBRReferenceCatalog(
                    tenant_id=tenant_id,
                    catalog_key=catalog_key,
                    request_fingerprint=request_fingerprint,
                    source=source,
                    source_version="1.12",
                    payload=serialized,
                    record_count=record_count,
                    fetched_at=now,
                    effective_date=effective_date,
                    expires_at=expires,
                    status="ACTIVE",
                    official_live_verified=official_live_verified,
                    last_error=last_error,
                )
                db.add(row)
            db.commit()
            db.refresh(row)
            return row
        except Exception as exc:
            db.rollback()
            logger.warning("Failed to upsert FBRReferenceCatalog: %s", exc)
            return None

    def _read_db_catalog(
        self,
        db: Optional[Session],
        *,
        tenant_id: Optional[str],
        catalog_key: str,
        request_fingerprint: str,
    ) -> Optional[Tuple[Any, FBRReferenceCatalog, bool]]:
        if db is None:
            return None
        row = (
            db.query(FBRReferenceCatalog)
            .filter(
                FBRReferenceCatalog.tenant_id == tenant_id,
                FBRReferenceCatalog.catalog_key == catalog_key,
                FBRReferenceCatalog.request_fingerprint == request_fingerprint,
            )
            .first()
        )
        if not row and tenant_id is not None:
            # Check global catalog row (tenant_id IS NULL)
            row = (
                db.query(FBRReferenceCatalog)
                .filter(
                    FBRReferenceCatalog.tenant_id.is_(None),
                    FBRReferenceCatalog.catalog_key == catalog_key,
                    FBRReferenceCatalog.request_fingerprint == request_fingerprint,
                )
                .first()
            )
        if not row:
            return None
        try:
            parsed = json.loads(row.payload)
        except Exception:
            return None
        now = datetime.now(timezone.utc)
        exp = row.expires_at
        if exp and exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        is_stale = bool(exp and now > exp)
        return parsed, row, is_stale

    async def _request_upstream(
        self,
        endpoint_path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        transport_strategy: Optional[StatlTransportStrategy] = None,
        token: str,
    ) -> Any:
        """Execute an authenticated HTTP call to PRAL gateway.
        Never executes without a token. Maps HTTP errors to domain exceptions.
        """
        if not token or not token.strip():
            raise CredentialsMissingError(
                f"Cannot call PRAL endpoint {endpoint_path} without a configured Bearer token."
            )

        url = f"{self.base_url}{endpoint_path}"
        headers = self._get_headers(token=token)
        strategy = transport_strategy or StatlTransportStrategy.QUERY_PARAMS

        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                if json_body is not None and strategy == StatlTransportStrategy.JSON_BODY_GET:
                    resp = await client.request("GET", url, headers=headers, json=json_body)
                elif json_body is not None and strategy == StatlTransportStrategy.POST_FALLBACK:
                    resp = await client.post(url, headers=headers, json=json_body)
                else:
                    q_params = params if params is not None else json_body
                    resp = await client.get(url, headers=headers, params=q_params)
        except httpx.TimeoutException as exc:
            raise UpstreamUnavailableError(f"Timeout contacting PRAL endpoint {endpoint_path}: {exc}")
        except httpx.RequestError as exc:
            raise UpstreamUnavailableError(f"Network error contacting PRAL endpoint {endpoint_path}: {exc}")

        if resp.status_code in (401, 403):
            raise UnauthorizedError(
                f"PRAL endpoint {endpoint_path} rejected authorization token (HTTP {resp.status_code})."
            )
        if resp.status_code in (400, 404, 422):
            raise InvalidRequestError(
                f"PRAL endpoint {endpoint_path} returned HTTP {resp.status_code}."
            )
        if resp.status_code >= 500:
            raise UpstreamUnavailableError(
                f"PRAL endpoint {endpoint_path} returned server error HTTP {resp.status_code}."
            )
        if resp.status_code != 200:
            raise UpstreamUnavailableError(
                f"PRAL endpoint {endpoint_path} returned unexpected HTTP {resp.status_code}."
            )

        try:
            return resp.json()
        except Exception as exc:
            raise SchemaDriftError(f"PRAL endpoint {endpoint_path} returned non-JSON body: {exc}")

    # ------------------------------------------------------------------
    # Normalization helpers (preserving both normalized & wire keys)
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_provinces(raw_list: List[Any]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for row in raw_list:
            try:
                wire = WireProvinceItem.model_validate(row)
            except Exception as exc:
                raise SchemaDriftError(f"Invalid province schema from PRAL: {exc}")
            out.append({
                "id": wire.stateProvinceCode,
                "code": str(wire.stateProvinceCode),
                "label": wire.stateProvinceDesc,
                "stateProvinceCode": wire.stateProvinceCode,
                "stateProvinceDesc": wire.stateProvinceDesc,
                "province_code": f"{wire.stateProvinceCode:02d}",
                "province_name": wire.stateProvinceDesc.title(),
            })
        return out

    @staticmethod
    def _normalize_doc_types(raw_list: List[Any]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for row in raw_list:
            try:
                wire = WireDocTypeItem.model_validate(row)
            except Exception as exc:
                raise SchemaDriftError(f"Invalid doctypecode schema from PRAL: {exc}")
            out.append({
                "id": wire.docTypeId,
                "code": str(wire.docTypeId),
                "label": wire.docDescription,
                "docTypeId": wire.docTypeId,
                "docDescription": wire.docDescription,
                "doc_type_code": str(wire.docTypeId),
                "doc_type_name": wire.docDescription,
            })
        return out

    @staticmethod
    def _normalize_item_codes(raw_list: List[Any]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for row in raw_list:
            try:
                wire = WireItemDescCodeItem.model_validate(row)
            except Exception as exc:
                raise SchemaDriftError(f"Invalid itemdesccode schema from PRAL: {exc}")
            out.append({
                "id": wire.hS_CODE,
                "code": wire.hS_CODE,
                "label": f"{wire.hS_CODE} — {wire.description}",
                "hS_CODE": wire.hS_CODE,
                "hs_code": wire.hS_CODE,
                "description": wire.description,
            })
        return out

    @staticmethod
    def _normalize_sro_item_codes(raw_list: List[Any]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for row in raw_list:
            try:
                wire = WireSroItemCodeItem.model_validate(row)
            except Exception as exc:
                raise SchemaDriftError(f"Invalid sroitemcode schema from PRAL: {exc}")
            out.append({
                "id": wire.srO_ITEM_ID,
                "code": str(wire.srO_ITEM_ID),
                "label": wire.srO_ITEM_DESC,
                "srO_ITEM_ID": wire.srO_ITEM_ID,
                "srO_ITEM_DESC": wire.srO_ITEM_DESC,
            })
        return out

    @staticmethod
    def _normalize_trans_types(raw_list: List[Any]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for row in raw_list:
            try:
                wire = WireTransTypeCodeItem.model_validate(row)
            except Exception as exc:
                raise SchemaDriftError(f"Invalid transtypecode schema from PRAL: {exc}")
            out.append({
                "id": wire.transactioN_TYPE_ID,
                "code": str(wire.transactioN_TYPE_ID),
                "label": wire.transactioN_DESC,
                "transactioN_TYPE_ID": wire.transactioN_TYPE_ID,
                "transactioN_DESC": wire.transactioN_DESC,
                "trans_type_code": str(wire.transactioN_TYPE_ID),
                "trans_type_name": wire.transactioN_DESC,
            })
        return out

    @staticmethod
    def _normalize_uoms(raw_list: List[Any]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for row in raw_list:
            try:
                wire = WireUomItem.model_validate(row)
            except Exception as exc:
                raise SchemaDriftError(f"Invalid uom schema from PRAL: {exc}")
            out.append({
                "id": wire.uoM_ID,
                "code": str(wire.uoM_ID),
                "label": wire.description,
                "uoM_ID": wire.uoM_ID,
                "description": wire.description,
                "uom_code": wire.description,
                "uom_name": wire.description,
            })
        return out

    @staticmethod
    def _normalize_sro_schedules(raw_list: List[Any]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for row in raw_list:
            try:
                wire = WireSroScheduleItem.model_validate(row)
            except Exception as exc:
                raise SchemaDriftError(f"Invalid SroSchedule schema from PRAL: {exc}")
            out.append({
                "id": wire.srO_ID,
                "code": str(wire.srO_ID),
                "label": wire.srO_DESC,
                "srO_ID": wire.srO_ID,
                "srO_DESC": wire.srO_DESC,
            })
        return out

    @staticmethod
    def _normalize_sale_type_rates(raw_list: List[Any]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for row in raw_list:
            try:
                wire = WireSaleTypeToRateItem.model_validate(row)
            except Exception as exc:
                raise SchemaDriftError(f"Invalid SaleTypeToRate schema from PRAL: {exc}")
            out.append({
                "id": wire.ratE_ID,
                "code": str(wire.ratE_ID),
                "label": wire.ratE_DESC,
                "rate_value": float(wire.ratE_VALUE),
                "ratE_ID": wire.ratE_ID,
                "ratE_DESC": wire.ratE_DESC,
                "ratE_VALUE": float(wire.ratE_VALUE),
            })
        return out

    @staticmethod
    def _normalize_hs_uoms(raw_list: List[Any], annexure_id: int) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for row in raw_list:
            try:
                wire = WireHsUomItem.model_validate(row)
            except Exception as exc:
                raise SchemaDriftError(f"Invalid HS_UOM schema from PRAL: {exc}")
            out.append({
                "id": wire.uoM_ID,
                "code": str(wire.uoM_ID),
                "label": wire.description,
                "annexure_id": annexure_id,
                "uoM_ID": wire.uoM_ID,
                "description": wire.description,
                "uom_code": wire.description,
                "uom_name": wire.description,
            })
        return out

    @staticmethod
    def _normalize_sro_items_by_schedule(raw_list: List[Any], sro_id: int) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for row in raw_list:
            try:
                wire = WireSroItemByScheduleItem.model_validate(row)
            except Exception as exc:
                raise SchemaDriftError(f"Invalid SROItem schema from PRAL: {exc}")
            out.append({
                "id": wire.srO_ITEM_ID,
                "code": str(wire.srO_ITEM_ID),
                "label": wire.srO_ITEM_DESC,
                "sro_id": sro_id,
                "srO_ITEM_ID": wire.srO_ITEM_ID,
                "srO_ITEM_DESC": wire.srO_ITEM_DESC,
            })
        return out

    # ------------------------------------------------------------------
    # Generic catalog execution engine (supports all 3 provider modes)
    # ------------------------------------------------------------------

    async def _execute_catalog_fetch(
        self,
        *,
        catalog_key: str,
        endpoint_path: str,
        params: Optional[Dict[str, Any]],
        normalizer,
        fixture_supplier,
        effective_date: Optional[str] = None,
        ttl_seconds: int = 86400,
        provider_mode: Optional[Union[str, ProviderMode]] = None,
        db: Optional[Session] = None,
        tenant_id: Optional[str] = None,
        allow_stale_on_error: bool = True,
    ) -> ReferenceEnvelope:
        fingerprint = build_request_fingerprint(catalog_key, params)
        token = self.resolve_token(db=db, tenant_id=tenant_id)

        # Resolve effective provider mode
        if provider_mode is not None:
            mode = ProviderMode(provider_mode) if not isinstance(provider_mode, ProviderMode) else provider_mode
        else:
            mode = ProviderMode.AUTHORIZED_LIVE if token else ProviderMode.FIXTURE

        # 1. AUTHORIZED_LIVE mode
        if mode == ProviderMode.AUTHORIZED_LIVE:
            if not token:
                self._record_sync_run(
                    db,
                    tenant_id=tenant_id,
                    catalog_key=catalog_key,
                    request_fingerprint=fingerprint,
                    provider_mode=mode.value,
                    outcome="SKIPPED_NO_CREDENTIALS",
                    error_code="CREDENTIALS_MISSING",
                    error_summary="PRAL Bearer token is not configured.",
                )
                raise CredentialsMissingError(
                    f"Cannot execute authorized_live lookup for '{catalog_key}': PRAL Bearer token is not configured."
                )
            try:
                raw = await self._request_upstream(endpoint_path, params=params, token=token)
                if not isinstance(raw, list):
                    raise SchemaDriftError(f"Expected JSON array from {endpoint_path}, got {type(raw).__name__}")
                normalized = normalizer(raw)
                now_iso = datetime.now(timezone.utc).isoformat()
                self._upsert_db_catalog(
                    db,
                    tenant_id=tenant_id,
                    catalog_key=catalog_key,
                    request_fingerprint=fingerprint,
                    source=DataSourceTag.PRAL_LIVE.value,
                    payload_data=normalized,
                    record_count=len(normalized),
                    effective_date=effective_date,
                    ttl_seconds=ttl_seconds,
                    official_live_verified=True,
                )
                self._record_sync_run(
                    db,
                    tenant_id=tenant_id,
                    catalog_key=catalog_key,
                    request_fingerprint=fingerprint,
                    provider_mode=mode.value,
                    outcome="SUCCESS",
                    record_count=len(normalized),
                )
                return ReferenceEnvelope(
                    data=normalized,
                    items=normalized,
                    count=len(normalized),
                    catalog_key=catalog_key,
                    source=DataSourceTag.PRAL_LIVE.value,
                    provider_mode=mode.value,
                    official_live_verified=True,
                    as_of=now_iso,
                    effective_date=effective_date,
                    stale=False,
                    request_fingerprint=fingerprint,
                )
            except Exception as exc:
                err_code = getattr(exc, "code", "UPSTREAM_ERROR")
                self._record_sync_run(
                    db,
                    tenant_id=tenant_id,
                    catalog_key=catalog_key,
                    request_fingerprint=fingerprint,
                    provider_mode=mode.value,
                    outcome="FAILED",
                    error_code=err_code,
                    error_summary=str(exc),
                )
                # If DB has a cached copy and allow_stale_on_error is True, serve cached with stale warning
                cached_tuple = self._read_db_catalog(
                    db, tenant_id=tenant_id, catalog_key=catalog_key, request_fingerprint=fingerprint
                )
                if allow_stale_on_error and cached_tuple is not None:
                    cached_data, row, _ = cached_tuple
                    return ReferenceEnvelope(
                        data=cached_data,
                        items=cached_data,
                        count=len(cached_data) if isinstance(cached_data, list) else 1,
                        catalog_key=catalog_key,
                        source=row.source,
                        provider_mode=mode.value,
                        official_live_verified=bool(row.official_live_verified),
                        as_of=row.fetched_at.isoformat() if row.fetched_at else None,
                        effective_date=row.effective_date,
                        stale=True,
                        last_sync_error=str(exc),
                        request_fingerprint=fingerprint,
                        warning=f"Live PRAL refresh failed ({err_code}); serving cached dataset.",
                    )
                raise

        # 2. CACHED_OFFICIAL mode
        if mode == ProviderMode.CACHED_OFFICIAL:
            cached_tuple = self._read_db_catalog(
                db, tenant_id=tenant_id, catalog_key=catalog_key, request_fingerprint=fingerprint
            )
            if cached_tuple is None:
                raise StaleReferenceError(
                    f"No cached official catalog found for '{catalog_key}' ({fingerprint}) and live token is unavailable."
                )
            cached_data, row, is_stale = cached_tuple
            return ReferenceEnvelope(
                data=cached_data,
                items=cached_data,
                count=len(cached_data) if isinstance(cached_data, list) else 1,
                catalog_key=catalog_key,
                source=row.source,
                provider_mode=mode.value,
                official_live_verified=bool(row.official_live_verified),
                as_of=row.fetched_at.isoformat() if row.fetched_at else None,
                effective_date=row.effective_date,
                stale=is_stale,
                last_sync_error=row.last_error,
                request_fingerprint=fingerprint,
            )

        # 3. FIXTURE mode (explicitly labeled DEMO_FIXTURE; never probes gw.fbr.gov.pk unauthenticated)
        # First check if an official or fixture row is already stored in DB
        cached_tuple = self._read_db_catalog(
            db, tenant_id=tenant_id, catalog_key=catalog_key, request_fingerprint=fingerprint
        )
        if cached_tuple is not None:
            cached_data, row, is_stale = cached_tuple
            return ReferenceEnvelope(
                data=cached_data,
                items=cached_data,
                count=len(cached_data) if isinstance(cached_data, list) else 1,
                catalog_key=catalog_key,
                source=row.source,
                provider_mode=mode.value,
                official_live_verified=bool(row.official_live_verified),
                as_of=row.fetched_at.isoformat() if row.fetched_at else None,
                effective_date=row.effective_date or effective_date,
                stale=is_stale,
                last_sync_error=row.last_error,
                request_fingerprint=fingerprint,
                warning="Using non-live reference catalog (no PRAL token configured)." if not row.official_live_verified else None,
            )

        fixture_data = fixture_supplier()
        now_iso = datetime.now(timezone.utc).isoformat()
        self._upsert_db_catalog(
            db,
            tenant_id=tenant_id,
            catalog_key=catalog_key,
            request_fingerprint=fingerprint,
            source=DataSourceTag.DEMO_FIXTURE.value,
            payload_data=fixture_data,
            record_count=len(fixture_data),
            effective_date=effective_date,
            ttl_seconds=ttl_seconds,
            official_live_verified=False,
        )
        return ReferenceEnvelope(
            data=fixture_data,
            items=fixture_data,
            count=len(fixture_data),
            catalog_key=catalog_key,
            source=DataSourceTag.DEMO_FIXTURE.value,
            provider_mode=ProviderMode.FIXTURE.value,
            official_live_verified=False,
            as_of=now_iso,
            effective_date=effective_date,
            stale=False,
            request_fingerprint=fingerprint,
            warning="DEMO_FIXTURE dataset from PRAL v1.12 specification examples. Not live-verified with FBR.",
        )

    # ==================================================================
    # Section 5.1 — GET /pdi/v1/provinces
    # ==================================================================
    async def fetch_provinces_envelope(
        self,
        *,
        provider_mode: Optional[Union[str, ProviderMode]] = None,
        db: Optional[Session] = None,
        tenant_id: Optional[str] = None,
    ) -> ReferenceEnvelope:
        return await self._execute_catalog_fetch(
            catalog_key="provinces",
            endpoint_path="/pdi/v1/provinces",
            params=None,
            normalizer=self._normalize_provinces,
            fixture_supplier=lambda: list(FALLBACK_PROVINCES),
            ttl_seconds=86400 * 7,
            provider_mode=provider_mode,
            db=db,
            tenant_id=tenant_id,
        )

    async def get_provinces(self, db: Optional[Session] = None, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        env = await self.fetch_provinces_envelope(db=db, tenant_id=tenant_id)
        return env.data

    # ==================================================================
    # Section 5.2 — GET /pdi/v1/doctypecode
    # ==================================================================
    async def fetch_document_types_envelope(
        self,
        *,
        provider_mode: Optional[Union[str, ProviderMode]] = None,
        db: Optional[Session] = None,
        tenant_id: Optional[str] = None,
    ) -> ReferenceEnvelope:
        return await self._execute_catalog_fetch(
            catalog_key="doctypecode",
            endpoint_path="/pdi/v1/doctypecode",
            params=None,
            normalizer=self._normalize_doc_types,
            fixture_supplier=lambda: list(FALLBACK_DOC_TYPES),
            ttl_seconds=86400 * 7,
            provider_mode=provider_mode,
            db=db,
            tenant_id=tenant_id,
        )

    async def get_document_types(self, db: Optional[Session] = None, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        env = await self.fetch_document_types_envelope(db=db, tenant_id=tenant_id)
        return env.data

    # ==================================================================
    # Section 5.3 — GET /pdi/v1/itemdesccode (NO upstream input params!)
    # ==================================================================
    async def fetch_item_codes_envelope(
        self,
        *,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        provider_mode: Optional[Union[str, ProviderMode]] = None,
        db: Optional[Session] = None,
        tenant_id: Optional[str] = None,
    ) -> ReferenceEnvelope:
        # Upstream call strictly takes params=None per PDF Section 5.3 ("API requires no request input")
        env = await self._execute_catalog_fetch(
            catalog_key="itemdesccode",
            endpoint_path="/pdi/v1/itemdesccode",
            params=None,
            normalizer=self._normalize_item_codes,
            fixture_supplier=lambda: list(FALLBACK_COMMON_HS_CODES),
            ttl_seconds=86400,
            provider_mode=provider_mode,
            db=db,
            tenant_id=tenant_id,
        )
        items: List[Dict[str, Any]] = env.data or []
        if search and search.strip():
            q = search.strip().lower()
            items = [
                item for item in items
                if q in str(item.get("hS_CODE", "")).lower()
                or q in str(item.get("hs_code", "")).lower()
                or q in str(item.get("description", "")).lower()
            ]
        total_filtered = len(items)
        sliced = items[offset: offset + limit] if limit > 0 else items
        return env.model_copy(update={"data": sliced, "items": sliced, "count": total_filtered})

    async def get_hs_codes(
        self,
        search: Optional[str] = None,
        db: Optional[Session] = None,
        tenant_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        env = await self.fetch_item_codes_envelope(search=search, db=db, tenant_id=tenant_id)
        return env.data

    # ==================================================================
    # Section 5.4 — GET /pdi/v1/sroitemcode
    # ==================================================================
    async def fetch_sro_item_codes_envelope(
        self,
        *,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        provider_mode: Optional[Union[str, ProviderMode]] = None,
        db: Optional[Session] = None,
        tenant_id: Optional[str] = None,
    ) -> ReferenceEnvelope:
        env = await self._execute_catalog_fetch(
            catalog_key="sroitemcode",
            endpoint_path="/pdi/v1/sroitemcode",
            params=None,
            normalizer=self._normalize_sro_item_codes,
            fixture_supplier=lambda: list(FALLBACK_SRO_ITEM_CODES),
            ttl_seconds=86400,
            provider_mode=provider_mode,
            db=db,
            tenant_id=tenant_id,
        )
        items: List[Dict[str, Any]] = env.data or []
        if search and search.strip():
            q = search.strip().lower()
            items = [
                item for item in items
                if q in str(item.get("srO_ITEM_ID", "")).lower()
                or q in str(item.get("srO_ITEM_DESC", "")).lower()
            ]
        total_filtered = len(items)
        sliced = items[offset: offset + limit] if limit > 0 else items
        return env.model_copy(update={"data": sliced, "items": sliced, "count": total_filtered})

    async def get_sro_item_codes(self, db: Optional[Session] = None, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        env = await self.fetch_sro_item_codes_envelope(db=db, tenant_id=tenant_id)
        return env.data

    # ==================================================================
    # Section 5.5 — GET /pdi/v1/transtypecode
    # ==================================================================
    async def fetch_transaction_types_envelope(
        self,
        *,
        provider_mode: Optional[Union[str, ProviderMode]] = None,
        db: Optional[Session] = None,
        tenant_id: Optional[str] = None,
    ) -> ReferenceEnvelope:
        return await self._execute_catalog_fetch(
            catalog_key="transtypecode",
            endpoint_path="/pdi/v1/transtypecode",
            params=None,
            normalizer=self._normalize_trans_types,
            fixture_supplier=lambda: list(FALLBACK_TRANSACTION_TYPES),
            ttl_seconds=86400,
            provider_mode=provider_mode,
            db=db,
            tenant_id=tenant_id,
        )

    async def get_transaction_types(self, db: Optional[Session] = None, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        env = await self.fetch_transaction_types_envelope(db=db, tenant_id=tenant_id)
        return env.data

    # ==================================================================
    # Section 5.6 — GET /pdi/v1/uom
    # ==================================================================
    async def fetch_uoms_envelope(
        self,
        *,
        provider_mode: Optional[Union[str, ProviderMode]] = None,
        db: Optional[Session] = None,
        tenant_id: Optional[str] = None,
    ) -> ReferenceEnvelope:
        return await self._execute_catalog_fetch(
            catalog_key="uom",
            endpoint_path="/pdi/v1/uom",
            params=None,
            normalizer=self._normalize_uoms,
            fixture_supplier=lambda: list(FALLBACK_UOMS),
            ttl_seconds=86400 * 7,
            provider_mode=provider_mode,
            db=db,
            tenant_id=tenant_id,
        )

    async def get_uoms(self, db: Optional[Session] = None, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        env = await self.fetch_uoms_envelope(db=db, tenant_id=tenant_id)
        return env.data

    # ==================================================================
    # Section 5.7 — GET /pdi/v1/SroSchedule?rate_id=...&date=DD-Mon-YYYY&origination_supplier_csv=...
    # ==================================================================
    async def fetch_sro_schedules_envelope(
        self,
        *,
        rate_id: int,
        date: Optional[Union[str, date_type, datetime]] = None,
        origination_supplier_csv: Union[int, str] = 1,
        provider_mode: Optional[Union[str, ProviderMode]] = None,
        db: Optional[Session] = None,
        tenant_id: Optional[str] = None,
    ) -> ReferenceEnvelope:
        formatted_date = format_pral_dd_mon_yyyy(date)
        params = {
            "rate_id": int(rate_id),
            "date": formatted_date,
            "origination_supplier_csv": str(origination_supplier_csv),
        }
        return await self._execute_catalog_fetch(
            catalog_key="sro_schedule",
            endpoint_path="/pdi/v1/SroSchedule",
            params=params,
            normalizer=self._normalize_sro_schedules,
            fixture_supplier=lambda: list(FALLBACK_SRO_SCHEDULES),
            effective_date=formatted_date,
            ttl_seconds=43200,
            provider_mode=provider_mode,
            db=db,
            tenant_id=tenant_id,
        )

    async def get_sro_schedules(
        self,
        rate_id: int = 701,
        date: Optional[str] = None,
        origination_supplier_csv: Union[int, str] = 1,
        db: Optional[Session] = None,
        tenant_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        env = await self.fetch_sro_schedules_envelope(
            rate_id=rate_id,
            date=date,
            origination_supplier_csv=origination_supplier_csv,
            db=db,
            tenant_id=tenant_id,
        )
        return env.data

    # ==================================================================
    # Section 5.8 — GET /pdi/v2/SaleTypeToRate?date=DD-Mon-YYYY&transTypeId=...&originationSupplier=...
    # ==================================================================
    async def fetch_sale_type_rates_envelope(
        self,
        *,
        trans_type_id: int,
        origination_supplier: int,
        date: Optional[Union[str, date_type, datetime]] = None,
        provider_mode: Optional[Union[str, ProviderMode]] = None,
        db: Optional[Session] = None,
        tenant_id: Optional[str] = None,
    ) -> ReferenceEnvelope:
        formatted_date = format_pral_dd_mon_yyyy(date)
        params = {
            "date": formatted_date,
            "transTypeId": int(trans_type_id),
            "originationSupplier": int(origination_supplier),
        }

        def _fixture_rates() -> List[Dict[str, Any]]:
            if int(trans_type_id) in FALLBACK_SALE_TYPE_RATES:
                return list(FALLBACK_SALE_TYPE_RATES[int(trans_type_id)])
            return list(FALLBACK_SALE_TYPE_RATES[75])

        return await self._execute_catalog_fetch(
            catalog_key="sale_type_to_rate",
            endpoint_path="/pdi/v2/SaleTypeToRate",
            params=params,
            normalizer=self._normalize_sale_type_rates,
            fixture_supplier=_fixture_rates,
            effective_date=formatted_date,
            ttl_seconds=43200,
            provider_mode=provider_mode,
            db=db,
            tenant_id=tenant_id,
        )

    async def get_rates_for_sale_type(
        self,
        sale_type: str,
        date: Optional[str] = None,
        province: Optional[str] = None,
        trans_type_id: Optional[int] = None,
        origination_supplier: Optional[int] = None,
        db: Optional[Session] = None,
        tenant_id: Optional[str] = None,
    ) -> List[str]:
        """Legacy helper preserving backward compatibility while delegating to v1.12 rate lookup."""
        resolved_tt_id = trans_type_id
        if resolved_tt_id is None:
            st_low = (sale_type or "").lower()
            matching = next(
                (t["transactioN_TYPE_ID"] for t in FALLBACK_TRANSACTION_TYPES if st_low in t["transactioN_DESC"].lower()),
                None,
            )
            if matching is not None:
                resolved_tt_id = matching
            elif "exempt" in st_low:
                resolved_tt_id = 81
            elif "zero" in st_low or "dtre" in st_low or "export" in st_low:
                resolved_tt_id = 84
            elif "reduced" in st_low:
                resolved_tt_id = 80
            elif "service" in st_low:
                resolved_tt_id = 112
            elif "potassium" in st_low:
                resolved_tt_id = 115
            else:
                resolved_tt_id = 75

        resolved_prov_id = origination_supplier or 7
        if origination_supplier is None and province:
            p_low = province.lower()
            p_match = next(
                (p["stateProvinceCode"] for p in FALLBACK_PROVINCES if p_low in p["stateProvinceDesc"].lower() or p_low == p["province_code"].lower()),
                None,
            )
            if p_match is not None:
                resolved_prov_id = p_match

        env = await self.fetch_sale_type_rates_envelope(
            trans_type_id=resolved_tt_id,
            origination_supplier=resolved_prov_id,
            date=date,
            db=db,
            tenant_id=tenant_id,
        )
        return [str(r.get("ratE_DESC") or r.get("label")) for r in env.data]

    # ==================================================================
    # Section 5.9 — GET /pdi/v2/HS_UOM?hs_code=...&annexure_id=...
    # ==================================================================
    async def fetch_hs_uom_envelope(
        self,
        *,
        hs_code: str,
        annexure_id: int = 3,
        provider_mode: Optional[Union[str, ProviderMode]] = None,
        db: Optional[Session] = None,
        tenant_id: Optional[str] = None,
    ) -> ReferenceEnvelope:
        clean_hs = (hs_code or "").strip()
        if not clean_hs:
            raise InvalidRequestError("hs_code is required for /pdi/v2/HS_UOM")
        params = {
            "hs_code": clean_hs,
            "annexure_id": int(annexure_id),
        }

        def _fixture_hs_uoms() -> List[Dict[str, Any]]:
            if clean_hs == "5904.9000":
                return [
                    {
                        "id": 77, "code": "77", "label": "Square Meter",
                        "annexure_id": int(annexure_id),
                        "uoM_ID": 77, "description": "Square Meter",
                        "uom_code": "SQM", "uom_name": "Square Meter",
                    }
                ]
            match = next(
                (h for h in FALLBACK_COMMON_HS_CODES if h["hS_CODE"] == clean_hs or h["hs_code"] == clean_hs),
                None,
            )
            if match and "allowed_uoms" in match:
                allowed = set(match["allowed_uoms"])
                filtered = [
                    {**u, "annexure_id": int(annexure_id)}
                    for u in FALLBACK_UOMS
                    if u["description"] in allowed or u.get("uom_code") in allowed
                ]
                if filtered:
                    return filtered
            return [{**u, "annexure_id": int(annexure_id)} for u in FALLBACK_UOMS]

        return await self._execute_catalog_fetch(
            catalog_key="hs_uom",
            endpoint_path="/pdi/v2/HS_UOM",
            params=params,
            normalizer=lambda raw: self._normalize_hs_uoms(raw, int(annexure_id)),
            fixture_supplier=_fixture_hs_uoms,
            ttl_seconds=86400,
            provider_mode=provider_mode,
            db=db,
            tenant_id=tenant_id,
        )

    async def get_valid_uoms_for_hs_code(
        self,
        hs_code: str,
        annexure_id: int = 3,
        db: Optional[Session] = None,
        tenant_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        env = await self.fetch_hs_uom_envelope(
            hs_code=hs_code, annexure_id=annexure_id, db=db, tenant_id=tenant_id
        )
        return env.data

    # ==================================================================
    # Section 5.10 — GET /pdi/v2/SROItem?date=YYYY-MM-DD&sro_id=...
    # ==================================================================
    async def fetch_sro_items_by_schedule_envelope(
        self,
        *,
        sro_id: int,
        date: Optional[Union[str, date_type, datetime]] = None,
        provider_mode: Optional[Union[str, ProviderMode]] = None,
        db: Optional[Session] = None,
        tenant_id: Optional[str] = None,
    ) -> ReferenceEnvelope:
        iso_date = format_pral_iso_date(date)
        params = {
            "date": iso_date,
            "sro_id": int(sro_id),
        }

        def _fixture_sro_items() -> List[Dict[str, Any]]:
            return [
                {**item, "sro_id": int(sro_id)}
                for item in FALLBACK_SRO_ITEM_CODES
            ]

        return await self._execute_catalog_fetch(
            catalog_key="sro_item",
            endpoint_path="/pdi/v2/SROItem",
            params=params,
            normalizer=lambda raw: self._normalize_sro_items_by_schedule(raw, int(sro_id)),
            fixture_supplier=_fixture_sro_items,
            effective_date=iso_date,
            ttl_seconds=43200,
            provider_mode=provider_mode,
            db=db,
            tenant_id=tenant_id,
        )

    async def get_sro_items_by_schedule(
        self,
        sro_schedule_no: Union[int, str],
        date: Optional[str] = None,
        db: Optional[Session] = None,
        tenant_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        digits = "".join(c for c in str(sro_schedule_no) if c.isdigit())
        sro_id = int(digits) if digits else 389
        env = await self.fetch_sro_items_by_schedule_envelope(
            sro_id=sro_id, date=date, db=db, tenant_id=tenant_id
        )
        return env.data

    # ==================================================================
    # Section 5.11 — GET /dist/v1/statl (Ambiguous transport in PDF p. 32)
    # ==================================================================
    async def check_statl_envelope(
        self,
        *,
        regno: str,
        date: Optional[Union[str, date_type, datetime]] = None,
        provider_mode: Optional[Union[str, ProviderMode]] = None,
        transport_strategy: Optional[StatlTransportStrategy] = None,
        db: Optional[Session] = None,
        tenant_id: Optional[str] = None,
    ) -> ReferenceEnvelope:
        digits = "".join(c for c in str(regno or "") if c.isdigit())
        if len(digits) not in (7, 13):
            raise InvalidRequestError(
                f"Invalid regno '{regno}'. Expected 7-digit NTN or 13-digit CNIC."
            )
        iso_date = format_pral_iso_date(date)
        req_payload = {"regno": digits, "date": iso_date}
        fingerprint = build_request_fingerprint("statl", req_payload)
        strategy = transport_strategy or self.statl_transport_strategy
        token = self.resolve_token(db=db, tenant_id=tenant_id)

        if provider_mode is not None:
            mode = ProviderMode(provider_mode) if not isinstance(provider_mode, ProviderMode) else provider_mode
        else:
            mode = ProviderMode.AUTHORIZED_LIVE if token else ProviderMode.FIXTURE

        if mode == ProviderMode.AUTHORIZED_LIVE:
            if not token:
                self._record_sync_run(
                    db,
                    tenant_id=tenant_id,
                    catalog_key="statl",
                    request_fingerprint=fingerprint,
                    provider_mode=mode.value,
                    outcome="SKIPPED_NO_CREDENTIALS",
                    error_code="CREDENTIALS_MISSING",
                    error_summary="PRAL Bearer token is not configured for STATL lookup.",
                )
                raise CredentialsMissingError(
                    "Cannot verify live STATL status: PRAL Bearer token is not configured."
                )
            raw = await self._request_upstream(
                "/dist/v1/statl",
                params=req_payload if strategy == StatlTransportStrategy.QUERY_PARAMS else None,
                json_body=req_payload if strategy != StatlTransportStrategy.QUERY_PARAMS else None,
                transport_strategy=strategy,
                token=token,
            )
            if not isinstance(raw, dict):
                raise SchemaDriftError(f"Expected JSON object from /dist/v1/statl, got {type(raw).__name__}")
            wire = WireStatlResponse.model_validate(raw)
            status_str = (wire.status or "").strip()
            status_code_str = (wire.status_code or str(raw.get("status code", raw.get("statuscode", "")))).strip()
            is_active = status_str.lower() == "active"
            result_data = {
                "regno": digits,
                "ntn": digits,
                "date": iso_date,
                "status_code": status_code_str,
                "status code": status_code_str,
                "status": status_str or ("Active" if is_active else "In-Active"),
                "is_active": is_active,
                "verified_state": "verified_active" if is_active else "verified_inactive",
                "official_live_verified": True,
                "raw_response": raw,
            }
            now_iso = datetime.now(timezone.utc).isoformat()
            self._upsert_db_catalog(
                db,
                tenant_id=tenant_id,
                catalog_key="statl",
                request_fingerprint=fingerprint,
                source=DataSourceTag.PRAL_LIVE.value,
                payload_data=result_data,
                record_count=1,
                effective_date=iso_date,
                ttl_seconds=3600,
                official_live_verified=True,
            )
            self._record_sync_run(
                db,
                tenant_id=tenant_id,
                catalog_key="statl",
                request_fingerprint=fingerprint,
                provider_mode=mode.value,
                outcome="SUCCESS",
                record_count=1,
            )
            return ReferenceEnvelope(
                data=result_data,
                items=result_data,
                count=1,
                catalog_key="statl",
                source=DataSourceTag.PRAL_LIVE.value,
                provider_mode=mode.value,
                official_live_verified=True,
                as_of=now_iso,
                effective_date=iso_date,
                stale=False,
                transport_mode=strategy.value,
                request_fingerprint=fingerprint,
            )

        # Unverified / fixture mode: NEVER claim live FBR Active status without a token!
        unverified_data = {
            "regno": digits,
            "ntn": digits,
            "date": iso_date,
            "status_code": None,
            "status code": None,
            "status": "not_checked",
            "is_active": None,
            "verified_state": "not_checked",
            "official_live_verified": False,
            "inquiry_date": iso_date,
            "message": "PRAL token not configured; STATL active status cannot be verified offline.",
        }
        return ReferenceEnvelope(
            data=unverified_data,
            items=unverified_data,
            count=1,
            catalog_key="statl",
            source=DataSourceTag.DEMO_FIXTURE.value,
            provider_mode=ProviderMode.FIXTURE.value,
            official_live_verified=False,
            as_of=datetime.now(timezone.utc).isoformat(),
            effective_date=iso_date,
            stale=False,
            transport_mode=strategy.value,
            request_fingerprint=fingerprint,
            warning="STATL status is 'not_checked' because no PRAL Bearer token is configured. Transport (GET query vs JSON body) also requires live verification.",
        )

    async def check_statl_status(
        self,
        ntn_or_cnic: str,
        date: Optional[str] = None,
        db: Optional[Session] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        env = await self.check_statl_envelope(regno=ntn_or_cnic, date=date, db=db, tenant_id=tenant_id)
        return env.data

    # ==================================================================
    # Section 5.12 — GET /dist/v1/Get_Reg_Type (Ambiguous transport in PDF p. 33)
    # ==================================================================
    async def check_registration_type_envelope(
        self,
        *,
        registration_no: str,
        provider_mode: Optional[Union[str, ProviderMode]] = None,
        transport_strategy: Optional[StatlTransportStrategy] = None,
        db: Optional[Session] = None,
        tenant_id: Optional[str] = None,
    ) -> ReferenceEnvelope:
        digits = "".join(c for c in str(registration_no or "") if c.isdigit())
        if len(digits) not in (7, 13):
            raise InvalidRequestError(
                f"Invalid Registration_No '{registration_no}'. Expected 7-digit NTN or 13-digit CNIC."
            )
        req_payload = {"Registration_No": digits}
        fingerprint = build_request_fingerprint("get_reg_type", req_payload)
        strategy = transport_strategy or self.statl_transport_strategy
        token = self.resolve_token(db=db, tenant_id=tenant_id)

        if provider_mode is not None:
            mode = ProviderMode(provider_mode) if not isinstance(provider_mode, ProviderMode) else provider_mode
        else:
            mode = ProviderMode.AUTHORIZED_LIVE if token else ProviderMode.FIXTURE

        if mode == ProviderMode.AUTHORIZED_LIVE:
            if not token:
                self._record_sync_run(
                    db,
                    tenant_id=tenant_id,
                    catalog_key="get_reg_type",
                    request_fingerprint=fingerprint,
                    provider_mode=mode.value,
                    outcome="SKIPPED_NO_CREDENTIALS",
                    error_code="CREDENTIALS_MISSING",
                    error_summary="PRAL Bearer token is not configured for Get_Reg_Type lookup.",
                )
                raise CredentialsMissingError(
                    "Cannot verify live buyer registration type: PRAL Bearer token is not configured."
                )
            raw = await self._request_upstream(
                "/dist/v1/Get_Reg_Type",
                params=req_payload if strategy == StatlTransportStrategy.QUERY_PARAMS else None,
                json_body=req_payload if strategy != StatlTransportStrategy.QUERY_PARAMS else None,
                transport_strategy=strategy,
                token=token,
            )
            if not isinstance(raw, dict):
                raise SchemaDriftError(f"Expected JSON object from /dist/v1/Get_Reg_Type, got {type(raw).__name__}")
            wire = WireGetRegTypeResponse.model_validate(raw)
            raw_type = (wire.REGISTRATION_TYPE or "").strip()
            is_reg = raw_type.lower() == "registered" and wire.statuscode == "00"
            normalized_type = "Registered" if is_reg else "Unregistered"
            result_data = {
                "registration_no": digits,
                "statuscode": wire.statuscode,
                "REGISTRATION_NO": wire.REGISTRATION_NO or digits,
                "REGISTRATION_TYPE": raw_type or normalized_type,
                "normalized_type": normalized_type,
                "verified_state": "verified_registered" if is_reg else "verified_unregistered",
                "official_live_verified": True,
                "raw_response": raw,
            }
            now_iso = datetime.now(timezone.utc).isoformat()
            self._upsert_db_catalog(
                db,
                tenant_id=tenant_id,
                catalog_key="get_reg_type",
                request_fingerprint=fingerprint,
                source=DataSourceTag.PRAL_LIVE.value,
                payload_data=result_data,
                record_count=1,
                effective_date=None,
                ttl_seconds=3600,
                official_live_verified=True,
            )
            self._record_sync_run(
                db,
                tenant_id=tenant_id,
                catalog_key="get_reg_type",
                request_fingerprint=fingerprint,
                provider_mode=mode.value,
                outcome="SUCCESS",
                record_count=1,
            )
            return ReferenceEnvelope(
                data=result_data,
                items=result_data,
                count=1,
                catalog_key="get_reg_type",
                source=DataSourceTag.PRAL_LIVE.value,
                provider_mode=mode.value,
                official_live_verified=True,
                as_of=now_iso,
                stale=False,
                transport_mode=strategy.value,
                request_fingerprint=fingerprint,
            )

        unverified_data = {
            "registration_no": digits,
            "statuscode": None,
            "REGISTRATION_NO": digits,
            "REGISTRATION_TYPE": "unknown",
            "normalized_type": "unknown",
            "verified_state": "not_checked",
            "official_live_verified": False,
            "message": "PRAL token not configured; buyer registration type must be selected manually in draft mode.",
        }
        return ReferenceEnvelope(
            data=unverified_data,
            items=unverified_data,
            count=1,
            catalog_key="get_reg_type",
            source=DataSourceTag.DEMO_FIXTURE.value,
            provider_mode=ProviderMode.FIXTURE.value,
            official_live_verified=False,
            as_of=datetime.now(timezone.utc).isoformat(),
            stale=False,
            transport_mode=strategy.value,
            request_fingerprint=fingerprint,
            warning="Registration type is 'unknown' / 'not_checked' because no PRAL Bearer token is configured.",
        )

    async def get_registration_types(
        self,
        registration_no: Optional[str] = None,
        db: Optional[Session] = None,
        tenant_id: Optional[str] = None,
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        if registration_no:
            env = await self.check_registration_type_envelope(
                registration_no=registration_no, db=db, tenant_id=tenant_id
            )
            return env.data
        return [
            {"reg_type_code": "01", "reg_type_name": "Registered"},
            {"reg_type_code": "02", "reg_type_name": "Unregistered"},
        ]

    # ==================================================================
    # Admin Reference Readiness & Sync Management
    # ==================================================================
    def get_reference_readiness(
        self,
        db: Session,
        tenant_id: Optional[str] = None,
    ) -> ReferenceReadinessResponse:
        token_present = self.has_token(db=db, tenant_id=tenant_id)
        datasets: List[CatalogDatasetStatus] = []
        live_count = 0

        for cat_key, sec, path, _ttl in CATALOG_METADATA:
            rows = (
                db.query(FBRReferenceCatalog)
                .filter(FBRReferenceCatalog.catalog_key == cat_key)
                .order_by(FBRReferenceCatalog.fetched_at.desc())
                .all()
            )
            if rows:
                latest = rows[0]
                total_records = sum(r.record_count for r in rows)
                is_live = any(r.official_live_verified for r in rows)
                if is_live:
                    live_count += 1
                now = datetime.now(timezone.utc)
                exp = latest.expires_at
                if exp and exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                is_stale = bool(exp and now > exp)
                datasets.append(
                    CatalogDatasetStatus(
                        catalog_key=cat_key,
                        section=sec,
                        endpoint_path=path,
                        cached_count=total_records,
                        source=latest.source,
                        official_live_verified=bool(latest.official_live_verified),
                        last_fetched_at=latest.fetched_at.isoformat() if latest.fetched_at else None,
                        expires_at=latest.expires_at.isoformat() if latest.expires_at else None,
                        stale=is_stale,
                        last_error=latest.last_error,
                    )
                )
            else:
                datasets.append(
                    CatalogDatasetStatus(
                        catalog_key=cat_key,
                        section=sec,
                        endpoint_path=path,
                        cached_count=0,
                        source=DataSourceTag.DEMO_FIXTURE.value,
                        official_live_verified=False,
                        stale=False,
                    )
                )

        runs = (
            db.query(FBRReferenceSyncRun)
            .order_by(FBRReferenceSyncRun.started_at.desc())
            .limit(20)
            .all()
        )
        recent_runs = [
            {
                "id": r.id,
                "catalog_key": r.catalog_key,
                "provider_mode": r.provider_mode,
                "outcome": r.outcome,
                "record_count": r.record_count,
                "error_code": r.error_code,
                "error_summary": r.error_summary,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "triggered_by": r.triggered_by,
            }
            for r in runs
        ]

        return ReferenceReadinessResponse(
            pral_token_configured=token_present,
            default_provider_mode=ProviderMode.AUTHORIZED_LIVE.value if token_present else ProviderMode.FIXTURE.value,
            statl_transport_strategy=self.statl_transport_strategy.value,
            official_live_verified_count=live_count,
            total_endpoints=12,
            datasets=datasets,
            recent_sync_runs=recent_runs,
        )

    async def sync_master_catalogs(
        self,
        db: Session,
        *,
        provider_mode: Optional[Union[str, ProviderMode]] = None,
        tenant_id: Optional[str] = None,
        triggered_by: str = "admin",
    ) -> Dict[str, Any]:
        """Synchronize the 6 parameterless master dictionaries (5.1 - 5.6) plus default cascaded samples."""
        token = self.resolve_token(db=db, tenant_id=tenant_id)
        mode = ProviderMode(provider_mode) if provider_mode else (
            ProviderMode.AUTHORIZED_LIVE if token else ProviderMode.FIXTURE
        )
        results: Dict[str, Any] = {}
        errors: Dict[str, str] = {}

        tasks = [
            ("provinces", lambda: self.fetch_provinces_envelope(provider_mode=mode, db=db, tenant_id=tenant_id)),
            ("doctypecode", lambda: self.fetch_document_types_envelope(provider_mode=mode, db=db, tenant_id=tenant_id)),
            ("itemdesccode", lambda: self.fetch_item_codes_envelope(provider_mode=mode, db=db, tenant_id=tenant_id, limit=0)),
            ("sroitemcode", lambda: self.fetch_sro_item_codes_envelope(provider_mode=mode, db=db, tenant_id=tenant_id, limit=0)),
            ("transtypecode", lambda: self.fetch_transaction_types_envelope(provider_mode=mode, db=db, tenant_id=tenant_id)),
            ("uom", lambda: self.fetch_uoms_envelope(provider_mode=mode, db=db, tenant_id=tenant_id)),
        ]

        for key, fn in tasks:
            try:
                env = await fn()
                results[key] = {
                    "status": "SYNCED",
                    "source": env.source,
                    "count": env.count,
                    "official_live_verified": env.official_live_verified,
                }
            except Exception as exc:
                errors[key] = str(exc)
                results[key] = {
                    "status": "FAILED",
                    "error": str(exc),
                }

        return {
            "provider_mode": mode.value,
            "pral_token_configured": bool(token),
            "official_live_verified": bool(token and not errors and mode == ProviderMode.AUTHORIZED_LIVE),
            "results": results,
            "errors": errors,
        }


# Singleton default instance and class alias
PRALReferenceService = PralReferenceService
pral_reference_service = PralReferenceService()
