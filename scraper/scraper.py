import json
import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

API_BASE = "https://txmccs.txdmv.gov/api/TruckStop"
HEADERS = {"Accept": "application/json"}

# Seed list of known AV operator authorization numbers
KNOWN_OPERATOR_IDS = [
    "AV8313426653583",  # Tesla Robotaxi, LLC
    "AV8712526941758",  # Waymo LLC
    "AV3411026312345",  # BOT AUTO TX INC
    "AV1112826519229",  # Zoox, Inc.
    "AV6911226417664",  # KODIAK ROBOTICS INC
    "AV2312026781376",  # AURORA (may appear as AURORA INNOVATION INC)
    "AV5211226394189",  # MAY MOBILITY INC
    "AV4914126484158",  # NURO INC
    "AV7514626642616",  # GATIK AI INCORPORATED
    "AV4314726144439",  # TORC ROBOTICS INC
    "AV4714826624272",  # WAABI
    "AV9714626911749",  # PLUSAI INC
    "AV1211026841314",  # TRUCK OPCO LLC
    "AV6514726251949",  # INTERNATIONAL TRANSPORT ENGINEERING LLC
]

# Search terms to discover new operators not in the seed list
SEARCH_TERMS = ["LLC", "Inc", "Corp", "AI", "Robotics", "Auto", "Mobility"]


def _clean_company_name(name: str) -> str:
    """Strip trailing DBA suffix from companyName fields."""
    if not name:
        return ""
    if ", DBA:" in name:
        name = name.split(", DBA:")[0]
    return name.strip()


def parse_company(api_response: dict) -> dict:
    """
    Extract operator fields from company detail or search result.

    New TxMCCS shape (2026-07-30+):
      companyName, autonomousVehicleAuthorizationNumber,
      autonomousVehicleStatus, businessEntityId
    """
    return {
        "name": _clean_company_name(api_response.get("companyName", "") or ""),
        "permit_number": api_response.get("autonomousVehicleAuthorizationNumber", "") or "",
        "status": api_response.get("autonomousVehicleStatus", "") or "",
        "business_entity_id": api_response.get("businessEntityId", "") or "",
    }


# Backwards-compatible alias used by older tests / callers
def parse_operator_detail(api_response: dict) -> dict:
    """
    Accept either new company payload or legacy operator wrapper.

    Legacy:
      {"operator": {"legalName", "authorizationNumber", "status"}}
    New:
      {"companyName", "autonomousVehicleAuthorizationNumber", ...}
      or {"operator": {...company fields...}}
    """
    if "companyName" in api_response or "autonomousVehicleAuthorizationNumber" in api_response:
        return parse_company(api_response)

    op = api_response.get("operator", {})
    # New fields nested under operator
    if "companyName" in op or "autonomousVehicleAuthorizationNumber" in op:
        return parse_company(op)

    # Fully legacy shape
    return {
        "name": op.get("legalName", "") or _clean_company_name(op.get("companyName", "")),
        "permit_number": op.get("authorizationNumber", "")
        or op.get("autonomousVehicleAuthorizationNumber", "")
        or "",
        "status": op.get("status", "") or op.get("autonomousVehicleStatus", "") or "",
        "business_entity_id": op.get("businessEntityId", "") or "",
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
        key = (v.get("make", "").strip().upper(), v.get("model", "").strip(), v.get("modelYear"))
        composition_counts[key] = composition_counts.get(key, 0) + 1

    dominant_model = max(model_counts, key=lambda m: model_counts[m]) if model_counts else ""

    composition = sorted(
        [
            {"make": make.upper(), "model": model, "year": year, "count": cnt}
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


def _search_companies(
    client: httpx.Client,
    query: str,
    search_type: str = "company_name",
) -> list[dict]:
    """
    Search companies. Returns only results that have an AV authorization number.
    """
    try:
        r = client.get(
            f"{API_BASE}/companies",
            params={"searchType": search_type, "searchValue": query},
            headers=HEADERS,
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        results = []
        for reg in data.get("results", []):
            if reg.get("autonomousVehicleAuthorizationNumber") and reg.get("businessEntityId"):
                results.append(reg)
        return results
    except Exception as e:
        logger.warning("Search failed for query %r (type=%s): %s", query, search_type, e)
        return []


def scrape_all_operators() -> tuple[list[dict], list[str]]:
    """
    Discover all AV operators and fetch their fleet data.

    Returns:
      (results, failures) where results is a list of operator+vehicle dicts
      ready to write to DB, and failures is a list of error strings.
    """
    failures: list[str] = []

    with httpx.Client(timeout=20.0) as client:
        # auth_number -> company search result (has businessEntityId)
        discovered: dict[str, dict] = {}

        # 1) Resolve known seed IDs via authorization-number search
        #    (name search alone can miss operators like Aurora)
        for op_id in KNOWN_OPERATOR_IDS:
            for reg in _search_companies(
                client, op_id, search_type="autonomous_vehicle_authorization_number"
            ):
                auth = reg["autonomousVehicleAuthorizationNumber"]
                discovered[auth] = reg

        # 2) Discover additional operators via name search
        for term in SEARCH_TERMS:
            for reg in _search_companies(client, term, search_type="company_name"):
                auth = reg["autonomousVehicleAuthorizationNumber"]
                discovered[auth] = reg

        logger.info("Scraping %d operators", len(discovered))

        if not discovered:
            failures.append("No operators discovered via TxMCCS search")
            return [], failures

        results = []
        for auth in sorted(discovered.keys()):
            company = discovered[auth]
            be_id = company["businessEntityId"]
            try:
                r_detail = client.get(
                    f"{API_BASE}/companies/{be_id}",
                    headers=HEADERS,
                    timeout=15,
                )
                r_detail.raise_for_status()
                detail_json = r_detail.json()

                r_vehicles = client.get(
                    f"{API_BASE}/companies/{be_id}/automated-motor-vehicles",
                    headers=HEADERS,
                    timeout=15,
                )
                r_vehicles.raise_for_status()
                vehicles_json = r_vehicles.json()

                # Prefer detail payload; fall back to search result fields
                op_data = parse_company({**company, **detail_json})
                # Ensure permit_number is the auth number even if detail omits it
                if not op_data["permit_number"]:
                    op_data["permit_number"] = auth

                veh_data = parse_vehicles_response(vehicles_json)

                results.append({
                    "operator_id": auth,
                    "name": op_data["name"] or company.get("companyName", auth),
                    "permit_number": op_data["permit_number"] or auth,
                    "status": op_data["status"] or company.get("autonomousVehicleStatus", ""),
                    "vehicle_count": veh_data["vehicle_count"],
                    "vehicle_type": veh_data["vehicle_type"],
                    "vehicle_composition": veh_data["vehicle_composition"],
                    "raw_json": json.dumps({
                        "detail": detail_json,
                        "vehicles": vehicles_json,
                    }),
                })
                logger.info(
                    "Scraped %s: %s (%d vehicles)",
                    auth,
                    op_data["name"],
                    veh_data["vehicle_count"],
                )
            except Exception as e:
                msg = f"{auth}: {e}"
                logger.error("Failed to scrape operator %s: %s", auth, e)
                failures.append(msg)

        return results, failures
