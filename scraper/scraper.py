import json
import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

API_BASE = "https://txmccs.txdmv.gov/api/TruckStop"
HEADERS = {"Accept": "application/json"}

# TxMCCS vehicle list (2026-09-03+): default page size 20, max limit 100,
# response shape {vehicles, total}. Counting len(vehicles) without paging
# silently caps every large fleet at 20.
VEHICLE_PAGE_SIZE = 100
_VEHICLE_OFFSET_GUARD = 100_000


class IncompleteVehicleList(RuntimeError):
    """Paginated vehicle fetch collected fewer records than the API `total`."""

# Known AV operators: (auth_number, business_entity_id, company_name_search)
# Primary discovery is company_name search + hardcoded businessEntityId fallback.
# Auth-number search (searchType=autonomous_vehicle_authorization_number) currently
# returns total=0 for all known AV numbers (verified 2026-09-01) and must not be
# the only seed path.
KNOWN_OPERATORS = [
    ("AV8313426653583", "81edcff1-8a6e-4ed0-be1f-60668515e223", "Tesla Robotaxi"),
    ("AV8712526941758", "07ebbc43-ae5b-42ca-a712-d9d5ce5b3516", "Waymo"),
    ("AV3411026312345", "a984e056-d778-416b-af45-03188239089c", "BOT AUTO"),
    ("AV1112826519229", "b5672c35-0996-4364-8ac7-080ea0333d2c", "Zoox"),
    ("AV6911226417664", "51e635a0-1649-419d-86b4-76a3107e3240", "Kodiak"),
    ("AV2312026781376", "e2ec8d3a-51c0-47fd-8172-49b1ca545ad3", "Aurora"),
    ("AV5211226394189", "2fb8d9e8-5add-4c1e-b746-58494b3661d8", "May Mobility"),
    ("AV4914126484158", "a073be41-e321-4074-9515-01279a9f36d7", "Nuro"),
    ("AV7514626642616", "c7252bd3-9b9a-4dfe-98e2-db205010f93c", "Gatik"),
    ("AV4314726144439", "fcf5ffd0-e90d-4aa6-9afa-6c002c2cf511", "Torc"),
    ("AV4714826624272", "43448d49-5ea9-4769-afcb-ffc5ca3f3cbb", "Waabi"),
    ("AV9714626911749", "15d49349-4d6f-4357-9138-b50547a027ad", "PlusAI"),
    ("AV1211026841314", "f77bbbc9-8f1f-4272-861f-8bec46cd0587", "TRUCK OPCO"),
    ("AV6514726251949", "625de9a0-ac22-4bdd-80d5-fbe638bcd74f", "INTERNATIONAL TRANSPORT ENGINEERING"),
]

# Backwards-compatible list of auth numbers only
KNOWN_OPERATOR_IDS = [auth for auth, _, _ in KNOWN_OPERATORS]

# Specific operator name terms for discovery (preferred over broad LLC/Inc).
# Broad terms like LLC/Inc match tens of thousands of carriers (page size 20) and
# are nearly useless for AV discovery — keep them optional and secondary.
OPERATOR_NAME_TERMS = [
    "Tesla Robotaxi",
    "Robotaxi",
    "Waymo",
    "Zoox",
    "Aurora",
    "Kodiak",
    "May Mobility",
    "Nuro",
    "Gatik",
    "Torc",
    "Waabi",
    "PlusAI",
    "BOT AUTO",
    "TRUCK OPCO",
]

# Optional broad discovery (secondary). Default page size is 20; limit/offset works
# but broad matches (e.g. LLC total ~74000) rarely surface AV operators.
BROAD_SEARCH_TERMS = ["Robotics", "Mobility", "AI"]


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


def fetch_all_vehicles(client: httpx.Client, business_entity_id: str) -> dict:
    """
    Fetch the full automated-motor-vehicles list for a company.

    TxMCCS paginates this endpoint (default 20, max limit 100) and reports the
    real fleet size in `total`. Follow limit/offset until we have `total`
    unique vehicles. If the API ignores limit and returns the whole list in
    one shot, stop after that response.
    """
    url = f"{API_BASE}/companies/{business_entity_id}/automated-motor-vehicles"
    all_vehicles: list[dict] = []
    seen_vins: set[str] = set()
    offset = 0
    reported_total: Optional[int] = None

    while offset <= _VEHICLE_OFFSET_GUARD:
        r = client.get(
            url,
            params={"limit": VEHICLE_PAGE_SIZE, "offset": offset},
            headers=HEADERS,
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        batch = data.get("vehicles") or []
        if isinstance(data.get("total"), int):
            reported_total = data["total"]

        # Full unpaginated payload (legacy, or API ignored limit).
        if offset == 0 and (
            (reported_total is not None and len(batch) >= reported_total)
            or len(batch) > VEHICLE_PAGE_SIZE
        ):
            return {
                "vehicles": list(batch),
                "total": reported_total if reported_total is not None else len(batch),
            }

        new_count = 0
        for v in batch:
            vin = v.get("vin")
            if vin:
                if vin in seen_vins:
                    continue
                seen_vins.add(vin)
            all_vehicles.append(v)
            new_count += 1

        if reported_total is not None and len(all_vehicles) >= reported_total:
            break
        if not batch or new_count == 0:
            break
        if reported_total is None and len(batch) < VEHICLE_PAGE_SIZE:
            break
        offset += len(batch)

    if reported_total is not None and len(all_vehicles) < reported_total:
        raise IncompleteVehicleList(
            f"{business_entity_id}: got {len(all_vehicles)} of {reported_total} vehicles"
        )

    return {
        "vehicles": all_vehicles,
        "total": reported_total if reported_total is not None else len(all_vehicles),
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
        # Normalize make casing so "TESLA" and "Tesla" merge in composition
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
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> list[dict]:
    """
    Search companies. Returns only results that have an AV authorization number.

    Optional limit/offset: TxMCCS defaults to page size 20. Useful for paging
    large result sets; broad terms like LLC still rarely yield AV operators.
    """
    try:
        params: dict = {"searchType": search_type, "searchValue": query}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        r = client.get(
            f"{API_BASE}/companies",
            params=params,
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


def _seed_from_known_operators(client: httpx.Client) -> dict[str, dict]:
    """
    Seed known operators via company_name search, falling back to hardcoded
    businessEntityId when search misses (or auth-number search is broken).

    Returns auth_number -> company dict (must include businessEntityId).
    """
    discovered: dict[str, dict] = {}

    for auth, be_id, search_name in KNOWN_OPERATORS:
        found = None
        for reg in _search_companies(client, search_name, search_type="company_name"):
            if reg.get("autonomousVehicleAuthorizationNumber") == auth:
                found = reg
                break
            # Accept any AV hit for this search that matches our BE id
            if reg.get("businessEntityId") == be_id:
                found = reg
                break

        if found:
            auth_key = found["autonomousVehicleAuthorizationNumber"]
            discovered[auth_key] = found
            continue

        # Fallback: use hardcoded BE id directly so Tesla et al. are always scraped
        logger.info(
            "company_name search missed %s (%s); using hardcoded businessEntityId %s",
            auth,
            search_name,
            be_id,
        )
        discovered[auth] = {
            "autonomousVehicleAuthorizationNumber": auth,
            "businessEntityId": be_id,
            "companyName": search_name,
            "autonomousVehicleStatus": "",
        }

    return discovered


def scrape_all_operators() -> tuple[list[dict], list[str]]:
    """
    Discover all AV operators and fetch their fleet data.

    Discovery order:
      1) Known operators via company_name + hardcoded businessEntityId fallback
      2) Specific operator name terms (Waymo, Zoox, Robotaxi, ...)
      3) Optional broad terms (Robotics/Mobility/AI) — secondary only

    Auth-number search is intentionally not primary: as of 2026-09-01 it returns
    total=0 for all known AV authorization numbers.

    Returns:
      (results, failures) where results is a list of operator+vehicle dicts
      ready to write to DB, and failures is a list of error strings.
    """
    failures: list[str] = []

    with httpx.Client(timeout=20.0) as client:
        # auth_number -> company search result (has businessEntityId)
        discovered: dict[str, dict] = {}

        # 1) Seed known operators (company_name + BE id fallback)
        discovered.update(_seed_from_known_operators(client))

        # 2) Specific operator name discovery
        for term in OPERATOR_NAME_TERMS:
            for reg in _search_companies(client, term, search_type="company_name"):
                auth = reg["autonomousVehicleAuthorizationNumber"]
                discovered[auth] = reg

        # 3) Optional broad discovery (do not rely on this alone)
        for term in BROAD_SEARCH_TERMS:
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

                vehicles_json = fetch_all_vehicles(client, be_id)

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
