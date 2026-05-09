# =============================================================
# Hi-Tech Waste Management — e-SWIS Formatter Service
# Formats scheduled waste data for DOE e-SWIS consignment notes
# =============================================================

from __future__ import annotations

import logging
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)

# e-SWIS physical state codes
PHYSICAL_STATE_CODES = {
    "solid":  "S",
    "liquid": "L",
    "sludge": "SL",
    "gas":    "G",
}

# e-SWIS container type codes
CONTAINER_TYPE_CODES = {
    "drum_200l":    "D200",
    "ibc":          "IBC",
    "sealed_bag":   "SB",
    "bulk":         "BLK",
    "skip":         "SK",
    "tanker":       "TK",
}


def format_consignment_note_data(
    batch: dict[str, Any],
    client: dict[str, Any],
    consignment_note: dict[str, Any],
) -> dict[str, Any]:
    """
    Format a scheduled waste batch and consignment note into the
    structure required by the DOE e-SWIS portal.

    Args:
        batch:             ScheduledWasteBatch data dict
        client:            Client data dict
        consignment_note:  ConsignmentNote data dict

    Returns:
        Dict formatted for e-SWIS submission / PDF generation
    """
    physical_state = batch.get("physical_state", "solid")
    physical_state_code = PHYSICAL_STATE_CODES.get(physical_state, "S")

    container_type = batch.get("container_type", "")
    container_code = CONTAINER_TYPE_CODES.get(container_type.lower().replace(" ", "_"), "")

    transport_date = consignment_note.get("transport_date")
    if isinstance(transport_date, date):
        transport_date_str = transport_date.isoformat()
    else:
        transport_date_str = str(transport_date) if transport_date else ""

    return {
        # Generator (waste producer)
        "generator_name":    client.get("company_name", ""),
        "generator_address": client.get("address", ""),
        "generator_city":    client.get("city", ""),
        "generator_state":   client.get("state", ""),
        "generator_ssm":     client.get("ssm_number", ""),
        "generator_pic":     client.get("pic_name", ""),
        "generator_phone":   client.get("pic_phone", ""),

        # Waste details
        "sw_code":           batch.get("sw_code", ""),
        "waste_description": batch.get("waste_description", ""),
        "quantity_kg":       float(batch.get("quantity_kg", 0)),
        "physical_state":    physical_state,
        "physical_state_code": physical_state_code,
        "container_type":    container_type,
        "container_code":    container_code,
        "container_count":   batch.get("container_count", 1),
        "storage_start_date": str(batch.get("storage_start_date", "")),
        "storage_deadline":  str(batch.get("storage_deadline", "")),

        # Transporter (Hi-Tech)
        "transporter_name":         consignment_note.get("transporter_name", "Hi-Tech Waste Management Sdn. Bhd."),
        "transporter_vehicle_reg":  consignment_note.get("vehicle_registration", ""),
        "transport_date":           transport_date_str,
        "cenviro_reference":        consignment_note.get("cenviro_reference", ""),

        # Processing facility
        "processing_facility": consignment_note.get("processing_facility", ""),

        # Note metadata
        "note_number":   consignment_note.get("note_number", ""),
        "generated_at":  str(consignment_note.get("generated_at", "")),
        "status":        consignment_note.get("status", "draft"),
    }


def validate_sw_code(sw_code: str) -> dict[str, Any]:
    """
    Validate a SW code against the known First Schedule library.

    Returns:
        {
            "valid": bool,
            "sw_code": str,
            "description": str | None,
            "category": str | None,
        }
    """
    # Normalise: strip spaces, uppercase
    normalised = sw_code.strip().upper().replace(" ", " ")

    # Known SW codes (subset — full list should be loaded from DB)
    KNOWN_CODES = {
        "SW 102": ("Waste that contains cyanide", "inorganic"),
        "SW 104": ("Waste that contains mercury or mercury compounds", "inorganic"),
        "SW 204": ("Waste mineral oil/water mixtures or emulsions", "organic"),
        "SW 305": ("Used lubricating oil", "organic"),
        "SW 306": ("Waste fuel (petrol, diesel, fuel oil, spent fuel)", "organic"),
        "SW 322": ("Waste that contains polychlorinated biphenyls (PCBs)", "organic"),
        "SW 401": ("Clinical waste", "clinical"),
        "SW 408": ("Asbestos waste", "inorganic"),
        "SW 409": ("Used tyres", "organic"),
        "SW 410": ("Batteries", "inorganic"),
        "SW 420": ("Electronic waste", "electronic"),
        "SW 422": ("Waste photographic chemicals", "organic"),
        "SW 440": ("Pharmaceutical waste", "clinical"),
        "SW 501": ("Leachate from scheduled waste disposal facility", "inorganic"),
        "SW 503": ("Contaminated soil", "inorganic"),
    }

    if normalised in KNOWN_CODES:
        description, category = KNOWN_CODES[normalised]
        return {
            "valid": True,
            "sw_code": normalised,
            "description": description,
            "category": category,
        }

    return {
        "valid": False,
        "sw_code": normalised,
        "description": None,
        "category": None,
    }
