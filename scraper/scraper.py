import json
import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

API_BASE = "https://txmccs.txdmv.gov/api/TruckStop"
HEADERS = {"Accept": "application/json"}

# Seed list of known AV operator IDs (updated 2026-06-05)
KNOWN_OPERATOR_IDS = [
    "AV8313426653583",  # Tesla Robotaxi, LLC
    "AV8712526941758",  # Waymo LLC
    "AV3411026312345",  # BOT AUTO TX INC
    "AV1112826519229",  # Zoox, Inc.
    "AV6911226417664",  # KODIAK ROBOTICS INC
    "AV2312026781376",  # AURORA OPERATIONS INC
    "AV5211226394189",  # MAY MOBILITY INC
    "AV4914126484158",  # NURO INC
    "AV7514626642616",  # GATIK AI INCORPORATED
    "AV4314726144439",  # TORC ROBOTICS INC
    "AV4714826624272",  # WAABI LOGISTICS INC
    "AV9714626911749",  # PLUSAI INC
    "AV1211026841314",  # TRUCK OPCO LLC
    "AV6514726251949",  # INTERNATIONAL TRANSPORT ENGINEERING LLC
]

# Search terms to discover new operators not in the seed list
SEARCH_TERMS = ["LLC", "Inc", "Corp", "AI", "Robotics", "Auto", "Mobility"]


def parse_operator_detail(api_response: dict) -> dict:
    """Extract operator fields from /operators/{id} response."""
    op = api_response.get("operator", {})
    entity = op.get("businessEntity", {})
    return {
        "name": entity.get("legalName", ""),
        "permit_number": op.get("authorizationNumber", ""),
        "status": op.get("status", ""),
    }


def parse_vehicles_response(api_response: dict) -> dict:
    """Extract vehicle count, dominant model, and composition breakdown."""
    vehicles = api_response.get("vehicles", [])
    count = len(vehicles)
    if count == 0:
        return {"vehicle_count": 0, "vehicle_type": "", "vehicle_composition": []}

    model_counts: dict[str, int] = {}
    composition_counts: dict[tuple, int] = {}
    for v in vehicles:
        model = v.get("model", "").strip()
        if model:
            model_counts[model] = model_counts.get(model, 0) + 1
        key = (v.get("make", "").strip(), model, v.get("modelYear"))
        composition_counts[key] = composition_counts.get(key, 0) + 1

    dominant_model = max(model_counts, key=lambda m: model_counts[m]) if model_counts else ""

    composition = sorted(
        [
            {"make": make, "model": model, "year": year, "count": cnt}
            for (make, model, year), cnt in composition_counts.items()
        ],
        key=lambda x: x["count"],
        reverse=True,
    )

    return {
        "vehicle_count": count,
        "vehicle_type": dominant_model,
        "vehicle_composition": composition,
    }


def _search_operators(client: httpx.Client, query: str) -> list[str]:
    """Search for operator authorization numbers by keyword. Returns list of IDs."""
    try:
        r = client.get(
            f"{API_BASE}/companies",
            params={"searchType": "company_name", "searchValue": query},
            headers=HEADERS,
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        return [
            reg.get("authorizationNumber")
            for reg in data.get("autonomousVehicleRegistrations", [])
            if reg.get("authorizationNumber")
        ]
    except Exception as e:
        logger.warning("Search failed for query %r: %s", query, e)
        return []


def scrape_all_operators() -> list[dict]:
    """
    Discover all AV operators and fetch their fleet data.
    Returns list of dicts with operator+vehicle data, ready to write to DB.
    """
    with httpx.Client(timeout=20.0) as client:
        # Discover operator IDs via search + seed list
        discovered: set[str] = set(KNOWN_OPERATOR_IDS)
        for term in SEARCH_TERMS:
            ids = _search_operators(client, term)
            discovered.update(ids)

        logger.info("Scraping %d operators", len(discovered))

        results = []
        for op_id in sorted(discovered):
            try:
                # Fetch operator detail
                r_detail = client.get(
                    f"{API_BASE}/operators/{op_id}",
                    headers=HEADERS,
                    timeout=15,
                )
                r_detail.raise_for_status()

                # Fetch vehicle list
                r_vehicles = client.get(
                    f"{API_BASE}/operators/{op_id}/vehicles",
                    headers=HEADERS,
                    timeout=15,
                )
                r_vehicles.raise_for_status()

                op_data = parse_operator_detail(r_detail.json())
                veh_data = parse_vehicles_response(r_vehicles.json())

                results.append({
                    "operator_id": op_id,
                    "name": op_data["name"],
                    "permit_number": op_data["permit_number"],
                    "status": op_data["status"],
                    "vehicle_count": veh_data["vehicle_count"],
                    "vehicle_type": veh_data["vehicle_type"],
                    "raw_json": json.dumps({
                        "detail": r_detail.json(),
                        "vehicles": r_vehicles.json(),
                    }),
                })
                logger.info("Scraped %s: %s (%d vehicles)", op_id, op_data["name"], veh_data["vehicle_count"])
            except Exception as e:
                logger.error("Failed to scrape operator %s: %s", op_id, e)

        return results
