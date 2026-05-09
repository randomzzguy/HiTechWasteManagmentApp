# =============================================================
# Hi-Tech Waste Management — Carbon Calculator Service
# GHG Protocol Scope 3 Category 5 calculations
# Malaysia-specific emission factors
# =============================================================

from __future__ import annotations

from decimal import Decimal
from typing import Optional

# ---------------------------------------------------------------------------
# Malaysia-specific emission factors
# Sources: MyCC (Malaysia Carbon Calculator), IPCC AR6, WRAP methodology
# ---------------------------------------------------------------------------

# Transport emission factor: kg CO2e per litre of diesel
# Source: IPCC AR6 / Malaysia Energy Commission
DIESEL_EMISSION_FACTOR_KG_CO2E_PER_LITRE = Decimal("2.68")

# Landfill methane emission factor: kg CO2e per tonne of waste diverted
# Source: IPCC 2006 Guidelines, Malaysia landfill conditions
LANDFILL_AVOIDANCE_KG_CO2E_PER_TONNE = Decimal("467.0")

# Recycling credits (kg CO2e saved per tonne recycled)
# Source: WRAP Material Change for a Better Environment
RECYCLING_CREDITS_KG_CO2E_PER_TONNE: dict[str, Decimal] = {
    "paper":     Decimal("700.0"),   # Mixed paper/cardboard
    "pet":       Decimal("1500.0"),  # PET plastic
    "hdpe":      Decimal("1400.0"),  # HDPE plastic
    "aluminium": Decimal("9500.0"),  # Aluminium (high energy savings)
    "ferrous":   Decimal("1500.0"),  # Steel/ferrous metals
    "glass":     Decimal("300.0"),   # Glass
    "ewaste":    Decimal("2000.0"),  # Electronic waste (estimated)
    "default":   Decimal("500.0"),   # Generic recyclable
}

# Waste-to-energy credit: kg CO2e per tonne processed
# Based on avoided grid electricity (Malaysia grid factor: 0.694 kg CO2e/kWh)
WTE_CREDIT_KG_CO2E_PER_TONNE = Decimal("200.0")

# BSF bioconversion credit: kg CO2e per tonne of food waste diverted
# Avoids landfill methane + produces protein feed (replaces fishmeal)
BSF_CREDIT_KG_CO2E_PER_TONNE = Decimal("550.0")


# ---------------------------------------------------------------------------
# Core calculation functions
# ---------------------------------------------------------------------------


def calculate_transport_emissions(
    fuel_litres: float | Decimal,
) -> Decimal:
    """
    Calculate transport CO2e emissions from fuel consumption.

    Args:
        fuel_litres: Diesel consumed in litres

    Returns:
        Transport emissions in kg CO2e
    """
    return (Decimal(str(fuel_litres)) * DIESEL_EMISSION_FACTOR_KG_CO2E_PER_LITRE).quantize(
        Decimal("0.001")
    )


def calculate_landfill_avoidance(
    diverted_kg: float | Decimal,
) -> Decimal:
    """
    Calculate carbon credit for waste diverted from landfill.

    Args:
        diverted_kg: Weight of waste diverted from landfill in kg

    Returns:
        Landfill avoidance credit in kg CO2e
    """
    diverted_tonnes = Decimal(str(diverted_kg)) / Decimal("1000")
    return (diverted_tonnes * LANDFILL_AVOIDANCE_KG_CO2E_PER_TONNE).quantize(
        Decimal("0.001")
    )


def calculate_recycling_credit(
    material_breakdown_kg: dict[str, float | Decimal],
) -> Decimal:
    """
    Calculate carbon credit from material recycling.

    Args:
        material_breakdown_kg: Dict of material type -> weight in kg
            Keys: paper, pet, hdpe, aluminium, ferrous, glass, ewaste

    Returns:
        Total recycling credit in kg CO2e
    """
    total_credit = Decimal("0")
    for material, kg in material_breakdown_kg.items():
        if kg and float(kg) > 0:
            factor = RECYCLING_CREDITS_KG_CO2E_PER_TONNE.get(
                material.lower(), RECYCLING_CREDITS_KG_CO2E_PER_TONNE["default"]
            )
            tonnes = Decimal(str(kg)) / Decimal("1000")
            total_credit += tonnes * factor

    return total_credit.quantize(Decimal("0.001"))


def calculate_wte_credit(
    wte_kg: float | Decimal,
) -> Decimal:
    """
    Calculate carbon credit from waste-to-energy processing.

    Args:
        wte_kg: Weight of waste processed via WtE in kg

    Returns:
        WtE credit in kg CO2e
    """
    wte_tonnes = Decimal(str(wte_kg)) / Decimal("1000")
    return (wte_tonnes * WTE_CREDIT_KG_CO2E_PER_TONNE).quantize(Decimal("0.001"))


def calculate_bsf_credit(
    food_waste_kg: float | Decimal,
) -> Decimal:
    """
    Calculate carbon credit from BSF bioconversion of food waste.

    Args:
        food_waste_kg: Weight of food waste processed via BSF in kg

    Returns:
        BSF credit in kg CO2e
    """
    food_tonnes = Decimal(str(food_waste_kg)) / Decimal("1000")
    return (food_tonnes * BSF_CREDIT_KG_CO2E_PER_TONNE).quantize(Decimal("0.001"))


def calculate_net_carbon_impact(
    transport_emissions_kgco2e: Decimal,
    landfill_avoidance_kgco2e: Decimal,
    recycling_credit_kgco2e: Decimal,
    wte_credit_kgco2e: Decimal,
) -> Decimal:
    """
    Calculate net carbon impact for a job.

    Net = transport_emissions - landfill_avoidance - recycling_credit - wte_credit

    A negative value indicates a net environmental benefit
    (more carbon avoided than emitted).

    Returns:
        Net carbon impact in kg CO2e
    """
    return (
        transport_emissions_kgco2e
        - landfill_avoidance_kgco2e
        - recycling_credit_kgco2e
        - wte_credit_kgco2e
    ).quantize(Decimal("0.001"))


def calculate_diversion_rate(
    total_waste_kg: float | Decimal,
    diverted_kg: float | Decimal,
) -> Optional[Decimal]:
    """
    Calculate waste diversion rate as a percentage.

    Diversion rate = (diverted_kg / total_waste_kg) × 100

    Args:
        total_waste_kg: Total waste collected in kg
        diverted_kg:    Waste diverted from landfill (recyclables + BSF + WtE) in kg

    Returns:
        Diversion rate as a percentage (0-100), or None if total is zero
    """
    total = Decimal(str(total_waste_kg))
    if total <= 0:
        return None
    diverted = Decimal(str(diverted_kg))
    return (diverted / total * Decimal("100")).quantize(Decimal("0.01"))


def calculate_job_carbon_record(
    fuel_litres: float | Decimal,
    recyclable_kg: float | Decimal,
    material_breakdown_kg: dict[str, float | Decimal] | None,
    wte_kg: float | Decimal,
    bsf_kg: float | Decimal,
    methodology_notes: str | None = None,
) -> dict[str, Decimal | str | None]:
    """
    Calculate a complete carbon record for a single job.

    Returns a dict matching the CarbonRecord model fields.
    """
    transport = calculate_transport_emissions(fuel_litres)
    landfill = calculate_landfill_avoidance(
        float(recyclable_kg) + float(wte_kg) + float(bsf_kg)
    )
    recycling = calculate_recycling_credit(material_breakdown_kg or {})
    wte = calculate_wte_credit(wte_kg)
    net = calculate_net_carbon_impact(transport, landfill, recycling, wte)

    notes = methodology_notes or (
        "Calculated using Malaysia-specific emission factors: "
        f"diesel {DIESEL_EMISSION_FACTOR_KG_CO2E_PER_LITRE} kg CO2e/L, "
        f"landfill avoidance {LANDFILL_AVOIDANCE_KG_CO2E_PER_TONNE} kg CO2e/t. "
        "Recycling credits per WRAP methodology. "
        "BSF credit includes landfill avoidance + fishmeal substitution."
    )

    return {
        "transport_emissions_kgco2e": transport,
        "landfill_avoidance_kgco2e": landfill,
        "recycling_credit_kgco2e": recycling,
        "wte_credit_kgco2e": wte,
        "net_carbon_impact_kgco2e": net,
        "methodology_notes": notes,
    }
