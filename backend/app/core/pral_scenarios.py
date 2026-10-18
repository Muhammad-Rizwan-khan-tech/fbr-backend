"""Official PRAL / FBR Digital Invoicing API v1.12 Sandbox Scenario Registry.
Sourced from Technical Specification for DI API — User Manual, Version 1.12:
  - Section 9: 28 Sandbox Scenarios SN001–SN028 (p. 46)
  - Section 10: Business Activity & Sector Eligibility Matrix (pp. 47–51)
"""

from typing import Dict, Any, List, Optional


class PRALScenario:
    def __init__(
        self,
        scenario_id: str,
        name: str,
        sale_type: str,
        applicable_sectors: List[str],
        description: str,
        tax_rate: str = "18%",
        requires_buyer_ntn: bool = True,
        is_retail_only: bool = False,
    ):
        self.scenario_id = scenario_id  # SN001 - SN028
        self.name = name
        self.sale_type = sale_type
        self.applicable_sectors = applicable_sectors
        self.description = description
        self.tax_rate = tax_rate
        self.requires_buyer_ntn = requires_buyer_ntn
        self.is_retail_only = is_retail_only

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "sale_type": self.sale_type,
            "applicable_sectors": self.applicable_sectors,
            "description": self.description,
            "tax_rate": self.tax_rate,
            "requires_buyer_ntn": self.requires_buyer_ntn,
            "is_retail_only": self.is_retail_only,
        }


# Standard Business Activity Categories from Section 10
SECTOR_MANUFACTURER = "MANUFACTURER"
SECTOR_DISTRIBUTOR = "DISTRIBUTOR"
SECTOR_WHOLESALER = "WHOLESALER"
SECTOR_EXPORTER = "EXPORTER"
SECTOR_RETAILER = "RETAILER"
SECTOR_SERVICE_PROVIDER = "SERVICE_PROVIDER"
SECTOR_OTHER = "OTHER"

ALL_GENERAL_SECTORS = [
    SECTOR_MANUFACTURER,
    SECTOR_DISTRIBUTOR,
    SECTOR_WHOLESALER,
    SECTOR_EXPORTER,
    SECTOR_RETAILER,
    SECTOR_OTHER,
]

PRAL_SCENARIOS_REGISTRY: Dict[str, PRALScenario] = {
    "SN001": PRALScenario(
        scenario_id="SN001",
        name="Standard Rate to Registered Buyer",
        sale_type="Goods at standard rate",
        applicable_sectors=ALL_GENERAL_SECTORS,
        description="Sale of standard-rated goods (18% Sales Tax) to an active registered business buyer with valid NTN/CNIC.",
        tax_rate="18%",
        requires_buyer_ntn=True,
    ),
    "SN002": PRALScenario(
        scenario_id="SN002",
        name="Standard Rate to Unregistered Buyer",
        sale_type="Goods at standard rate",
        applicable_sectors=ALL_GENERAL_SECTORS,
        description="Sale of standard-rated goods to an unregistered buyer (default NTN 1111111 or CNIC), subject to further tax where applicable.",
        tax_rate="18%",
        requires_buyer_ntn=False,
    ),
    "SN003": PRALScenario(
        scenario_id="SN003",
        name="Steel Melting & Re-Rolling",
        sale_type="Steel sector",
        applicable_sectors=[SECTOR_MANUFACTURER, SECTOR_WHOLESALER],
        description="Supply of steel products under special steel tax provisions.",
        tax_rate="18%",
        requires_buyer_ntn=True,
    ),
    "SN004": PRALScenario(
        scenario_id="SN004",
        name="Ship Breaking",
        sale_type="Ship breaking",
        applicable_sectors=[SECTOR_MANUFACTURER, SECTOR_OTHER],
        description="Supplies arising from ship breaking activities under Eleventh Schedule.",
        tax_rate="18%",
        requires_buyer_ntn=True,
    ),
    "SN005": PRALScenario(
        scenario_id="SN005",
        name="Reduced Rate Goods",
        sale_type="Goods at reduced rate",
        applicable_sectors=ALL_GENERAL_SECTORS,
        description="Sale of goods under Eighth Schedule eligible for reduced tax rates (e.g. 1%, 2%, 5%, 10%).",
        tax_rate="Reduced",
        requires_buyer_ntn=True,
    ),
    "SN006": PRALScenario(
        scenario_id="SN006",
        name="Exempt Goods",
        sale_type="Exempt goods",
        applicable_sectors=ALL_GENERAL_SECTORS,
        description="Supplies exempt from Sales Tax under the Sixth Schedule to the Sales Tax Act, 1990.",
        tax_rate="0%",
        requires_buyer_ntn=False,
    ),
    "SN007": PRALScenario(
        scenario_id="SN007",
        name="Zero-Rated Goods",
        sale_type="Zero rated goods",
        applicable_sectors=[SECTOR_MANUFACTURER, SECTOR_EXPORTER, SECTOR_DISTRIBUTOR],
        description="Supplies taxed at 0% under the Fifth Schedule to the Sales Tax Act, 1990.",
        tax_rate="0%",
        requires_buyer_ntn=True,
    ),
    "SN008": PRALScenario(
        scenario_id="SN008",
        name="Third Schedule Goods (Retail Price)",
        sale_type="Third schedule goods",
        applicable_sectors=[SECTOR_MANUFACTURER, SECTOR_DISTRIBUTOR, SECTOR_WHOLESALER],
        description="Goods specified in the Third Schedule where sales tax is assessed on retail price rather than wholesale transaction value.",
        tax_rate="18%",
        requires_buyer_ntn=False,
    ),
    "SN009": PRALScenario(
        scenario_id="SN009",
        name="Electric Power Transmission",
        sale_type="Electricity supplies",
        applicable_sectors=[SECTOR_MANUFACTURER, SECTOR_OTHER],
        description="Supply and transmission of electric power subject to specific sales tax regimes.",
        tax_rate="18%",
        requires_buyer_ntn=True,
    ),
    "SN010": PRALScenario(
        scenario_id="SN010",
        name="Telecommunication Services",
        sale_type="Telecommunication services",
        applicable_sectors=[SECTOR_SERVICE_PROVIDER],
        description="Provision of telecommunication services subject to federal or provincial sales tax.",
        tax_rate="19.5%",
        requires_buyer_ntn=False,
    ),
    "SN011": PRALScenario(
        scenario_id="SN011",
        name="Petroleum Products",
        sale_type="Petroleum products",
        applicable_sectors=[SECTOR_DISTRIBUTOR, SECTOR_WHOLESALER, SECTOR_RETAILER],
        description="Sale of petroleum crude and refined fuels governed by the Petroleum Sales Tax rules.",
        tax_rate="Standard/Fixed",
        requires_buyer_ntn=False,
    ),
    "SN012": PRALScenario(
        scenario_id="SN012",
        name="Compressed Natural Gas (CNG)",
        sale_type="CNG supplies",
        applicable_sectors=[SECTOR_DISTRIBUTOR, SECTOR_RETAILER],
        description="Supply of Compressed Natural Gas through authorized stations.",
        tax_rate="Fixed",
        requires_buyer_ntn=False,
    ),
    "SN013": PRALScenario(
        scenario_id="SN013",
        name="Mobile Phones & Cellular Devices",
        sale_type="Mobile phones",
        applicable_sectors=[SECTOR_DISTRIBUTOR, SECTOR_WHOLESALER, SECTOR_RETAILER],
        description="Sale of mobile phones and cellular equipment under the Ninth Schedule fixed tax regime.",
        tax_rate="Fixed",
        requires_buyer_ntn=False,
    ),
    "SN014": PRALScenario(
        scenario_id="SN014",
        name="Potassium Chlorate",
        sale_type="Potassium chlorate",
        applicable_sectors=[SECTOR_MANUFACTURER, SECTOR_DISTRIBUTOR],
        description="Chemical supply of Potassium Chlorate subject to enhanced regulatory monitoring.",
        tax_rate="18%",
        requires_buyer_ntn=True,
    ),
    "SN015": PRALScenario(
        scenario_id="SN015",
        name="Sugar Supplies",
        sale_type="Sugar sector",
        applicable_sectors=[SECTOR_MANUFACTURER, SECTOR_WHOLESALER],
        description="Sale of refined sugar subject to track-and-trace stamps and sales tax rules.",
        tax_rate="18%",
        requires_buyer_ntn=True,
    ),
    "SN016": PRALScenario(
        scenario_id="SN016",
        name="Tea Supplies",
        sale_type="Tea sector",
        applicable_sectors=[SECTOR_MANUFACTURER, SECTOR_DISTRIBUTOR, SECTOR_WHOLESALER],
        description="Sale of processed or blended tea subject to specific schedule rules.",
        tax_rate="18%",
        requires_buyer_ntn=True,
    ),
    "SN017": PRALScenario(
        scenario_id="SN017",
        name="Goods with FED in Sales Tax Mode",
        sale_type="Goods with FED in ST mode",
        applicable_sectors=[SECTOR_MANUFACTURER, SECTOR_DISTRIBUTOR],
        description="Federal Excise Duty (FED) levied on goods collected in sales tax mode.",
        tax_rate="FED+ST",
        requires_buyer_ntn=True,
    ),
    "SN018": PRALScenario(
        scenario_id="SN018",
        name="Services with FED in Sales Tax Mode",
        sale_type="Services with FED in ST mode",
        applicable_sectors=[SECTOR_SERVICE_PROVIDER],
        description="Federal Excise Duty on services collected in sales tax mode.",
        tax_rate="FED+ST",
        requires_buyer_ntn=True,
    ),
    "SN019": PRALScenario(
        scenario_id="SN019",
        name="Provincial & Federal Services",
        sale_type="Services",
        applicable_sectors=[SECTOR_SERVICE_PROVIDER],
        description="Rendering of taxable services governed by provincial revenue authorities (SRB, PRA, BRA, KPRA) or ICT Ordinance.",
        tax_rate="15%",
        requires_buyer_ntn=False,
    ),
    "SN020": PRALScenario(
        scenario_id="SN020",
        name="Toll Manufacturing",
        sale_type="Toll manufacturing",
        applicable_sectors=[SECTOR_MANUFACTURER],
        description="Processing services rendered on principal's raw materials without transfer of title.",
        tax_rate="18%",
        requires_buyer_ntn=True,
    ),
    "SN021": PRALScenario(
        scenario_id="SN021",
        name="Goods Sold at Fixed Notified Value",
        sale_type="Fixed value goods",
        applicable_sectors=[SECTOR_MANUFACTURER, SECTOR_DISTRIBUTOR],
        description="Goods where minimum value for sales tax assessment is notified by the Board.",
        tax_rate="18%",
        requires_buyer_ntn=True,
    ),
    "SN022": PRALScenario(
        scenario_id="SN022",
        name="Cotton Ginners",
        sale_type="Cotton sector",
        applicable_sectors=[SECTOR_MANUFACTURER],
        description="Supply of raw cotton and lint by ginning factories under special sales tax provisions.",
        tax_rate="18%",
        requires_buyer_ntn=True,
    ),
    "SN023": PRALScenario(
        scenario_id="SN023",
        name="Commercial Importers",
        sale_type="Commercial imports",
        applicable_sectors=[SECTOR_DISTRIBUTOR, SECTOR_WHOLESALER],
        description="Subsequent local supply of commercial imports with value addition tax credit.",
        tax_rate="18%",
        requires_buyer_ntn=True,
    ),
    "SN024": PRALScenario(
        scenario_id="SN024",
        name="Export of Goods",
        sale_type="Export of goods",
        applicable_sectors=[SECTOR_EXPORTER, SECTOR_MANUFACTURER],
        description="Direct export of manufactured or commercial goods outside Pakistan (0% rate).",
        tax_rate="0%",
        requires_buyer_ntn=False,
    ),
    "SN025": PRALScenario(
        scenario_id="SN025",
        name="Non-Adjustable Supplies",
        sale_type="Non-adjustable supplies",
        applicable_sectors=ALL_GENERAL_SECTORS,
        description="Supplies in respect of which input tax is not admissible under section 8 of the Sales Tax Act, 1990.",
        tax_rate="18%",
        requires_buyer_ntn=False,
    ),
    # Retailer-specific Scenarios (Section 10, pp. 47–51: Strictly for registered Retailers)
    "SN026": PRALScenario(
        scenario_id="SN026",
        name="Retailer Sale to End Consumer (Standard Rate)",
        sale_type="Retailer sale at standard rate",
        applicable_sectors=[SECTOR_RETAILER],
        description="Tier-1 Retailer sale of standard-rated goods to an end consumer at point of sale.",
        tax_rate="18%",
        requires_buyer_ntn=False,
        is_retail_only=True,
    ),
    "SN027": PRALScenario(
        scenario_id="SN027",
        name="Retailer Sale of Third Schedule Goods",
        sale_type="Retailer sale of 3rd schedule",
        applicable_sectors=[SECTOR_RETAILER],
        description="Tier-1 Retailer sale of Third Schedule retail-price goods to end consumer.",
        tax_rate="18%",
        requires_buyer_ntn=False,
        is_retail_only=True,
    ),
    "SN028": PRALScenario(
        scenario_id="SN028",
        name="Retailer Sale at Reduced Rate",
        sale_type="Retailer sale at reduced rate",
        applicable_sectors=[SECTOR_RETAILER],
        description="Tier-1 Retailer sale of goods subject to concessionary or reduced rates to end consumer.",
        tax_rate="Reduced",
        requires_buyer_ntn=False,
        is_retail_only=True,
    ),
}


def get_scenarios_for_activity(business_activity: Optional[str]) -> List[PRALScenario]:
    """Filters applicable PRAL sandbox scenarios based on organization's registered business activity."""
    if not business_activity:
        # Default to standard general scenarios (excluding retail-only)
        return [s for s in PRAL_SCENARIOS_REGISTRY.values() if not s.is_retail_only]

    act_upper = business_activity.strip().upper()
    matching: List[PRALScenario] = []

    for s in PRAL_SCENARIOS_REGISTRY.values():
        if act_upper in s.applicable_sectors:
            matching.append(s)

    # If no exact sector matched, return general scenarios
    if not matching:
        return [s for s in PRAL_SCENARIOS_REGISTRY.values() if not s.is_retail_only]

    return matching


def is_scenario_eligible(scenario_id: str, business_activity: Optional[str]) -> bool:
    """Checks if a given scenario ID is eligible for the organization's business activity."""
    scenario = PRAL_SCENARIOS_REGISTRY.get(scenario_id.upper())
    if not scenario:
        return False
    if not business_activity:
        return not scenario.is_retail_only
    return business_activity.strip().upper() in scenario.applicable_sectors
