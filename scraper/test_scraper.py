import pytest
from scraper import (
    parse_operator_detail,
    parse_company,
    parse_vehicles_response,
    _seed_from_known_operators,
    fetch_all_vehicles,
    IncompleteVehicleList,
    KNOWN_OPERATORS,
    OPERATOR_NAME_TERMS,
    VEHICLE_PAGE_SIZE,
)


def test_parse_company_extracts_fields():
    api_response = {
        "businessEntityId": "81edcff1-8a6e-4ed0-be1f-60668515e223",
        "companyName": "Tesla Robotaxi, LLC, DBA: Tesla Robotaxi, LLC",
        "autonomousVehicleAuthorizationNumber": "AV8313426653583",
        "autonomousVehicleStatus": "authorized",
    }
    result = parse_company(api_response)
    assert result["name"] == "Tesla Robotaxi, LLC"
    assert result["permit_number"] == "AV8313426653583"
    assert result["status"] == "authorized"
    assert result["business_entity_id"] == "81edcff1-8a6e-4ed0-be1f-60668515e223"


def test_parse_company_handles_missing_fields():
    result = parse_company({})
    assert result["name"] == ""
    assert result["permit_number"] == ""
    assert result["status"] == ""
    assert result["business_entity_id"] == ""


def test_parse_operator_detail_new_company_shape():
    api_response = {
        "companyName": "Waymo LLC",
        "autonomousVehicleAuthorizationNumber": "AV8712526941758",
        "autonomousVehicleStatus": "authorized",
        "businessEntityId": "abc-123",
    }
    result = parse_operator_detail(api_response)
    assert result["name"] == "Waymo LLC"
    assert result["permit_number"] == "AV8712526941758"
    assert result["status"] == "authorized"


def test_parse_operator_detail_legacy_shape():
    api_response = {
        "operator": {
            "authorizationNumber": "AV8313426653583",
            "status": "authorized",
            "legalName": "Tesla Robotaxi, LLC",
        }
    }
    result = parse_operator_detail(api_response)
    assert result["name"] == "Tesla Robotaxi, LLC"
    assert result["permit_number"] == "AV8313426653583"
    assert result["status"] == "authorized"


def test_parse_operator_detail_handles_missing_fields():
    api_response = {"operator": {}}
    result = parse_operator_detail(api_response)
    assert result["name"] == ""
    assert result["permit_number"] == ""
    assert result["status"] == ""


def test_parse_vehicles_response_counts_vehicles():
    api_response = {
        "vehicles": [
            {"vin": "VIN1", "make": "TESLA", "model": "Model Y", "modelYear": 2026},
            {"vin": "VIN2", "make": "TESLA", "model": "Model Y", "modelYear": 2026},
        ]
    }
    result = parse_vehicles_response(api_response)
    assert result["vehicle_count"] == 2
    assert result["vehicle_type"] == "Model Y"


def test_parse_vehicles_response_empty():
    api_response = {"vehicles": []}
    result = parse_vehicles_response(api_response)
    assert result["vehicle_count"] == 0
    assert result["vehicle_type"] == ""


def test_parse_vehicles_response_mixed_models():
    api_response = {
        "vehicles": [
            {"vin": "VIN1", "make": "TESLA", "model": "Model Y", "modelYear": 2026},
            {"vin": "VIN2", "make": "TESLA", "model": "Model 3", "modelYear": 2026},
            {"vin": "VIN3", "make": "TESLA", "model": "Model Y", "modelYear": 2026},
        ]
    }
    result = parse_vehicles_response(api_response)
    assert result["vehicle_count"] == 3
    # vehicle_type should be most common model
    assert result["vehicle_type"] == "Model Y"


def test_parse_vehicles_response_all_missing_models():
    api_response = {
        "vehicles": [
            {"vin": "VIN1", "make": "TESLA"},  # no "model" key
            {"vin": "VIN2", "make": "TESLA"},
        ]
    }
    result = parse_vehicles_response(api_response)
    assert result["vehicle_count"] == 2
    assert result["vehicle_type"] == ""  # graceful empty, not a crash


def test_parse_vehicles_response_composition_single_group():
    api_response = {
        "vehicles": [
            {"vin": "VIN1", "make": "TESLA", "model": "Model Y", "modelYear": 2026},
            {"vin": "VIN2", "make": "TESLA", "model": "Model Y", "modelYear": 2026},
            {"vin": "VIN3", "make": "TESLA", "model": "Model Y", "modelYear": 2026},
        ]
    }
    result = parse_vehicles_response(api_response)
    assert result["vehicle_composition"] == [
        {"make": "TESLA", "model": "Model Y", "year": 2026, "count": 3}
    ]


def test_parse_vehicles_response_composition_multiple_groups_sorted():
    api_response = {
        "vehicles": [
            {"vin": "VIN1", "make": "TESLA", "model": "Cybercab", "modelYear": 2026},
            {"vin": "VIN2", "make": "TESLA", "model": "Model Y", "modelYear": 2026},
            {"vin": "VIN3", "make": "TESLA", "model": "Model Y", "modelYear": 2026},
            {"vin": "VIN4", "make": "TESLA", "model": "Model Y", "modelYear": 2025},
        ]
    }
    result = parse_vehicles_response(api_response)
    # sorted by count desc
    assert result["vehicle_composition"][0] == {"make": "TESLA", "model": "Model Y", "year": 2026, "count": 2}
    assert len(result["vehicle_composition"]) == 3
    cybercab = [c for c in result["vehicle_composition"] if c["model"] == "Cybercab"]
    assert cybercab == [{"make": "TESLA", "model": "Cybercab", "year": 2026, "count": 1}]


def test_parse_vehicles_response_composition_includes_cybercab():
    """Regression: Cybercab must appear in composition when present in fleet."""
    api_response = {
        "vehicles": [
            {"vin": "VIN1", "make": "TESLA", "model": "Model Y", "modelYear": 2026},
            {"vin": "VIN2", "make": "TESLA", "model": "Cybercab", "modelYear": 2026},
            {"vin": "VIN3", "make": "Tesla", "model": "Cybercab", "modelYear": 2026},
            {"vin": "VIN4", "make": "Tesla", "model": "Model Y", "modelYear": 2026},
        ]
    }
    result = parse_vehicles_response(api_response)
    assert result["vehicle_count"] == 4
    # make casing normalized so TESLA/Tesla merge
    by_model = {c["model"]: c for c in result["vehicle_composition"]}
    assert by_model["Model Y"]["count"] == 2
    assert by_model["Model Y"]["make"] == "TESLA"
    assert by_model["Cybercab"]["count"] == 2
    assert by_model["Cybercab"]["make"] == "TESLA"


def test_parse_vehicles_response_composition_empty():
    api_response = {"vehicles": []}
    result = parse_vehicles_response(api_response)
    assert result["vehicle_composition"] == []


def test_parse_vehicles_response_composition_null_year():
    api_response = {
        "vehicles": [
            {"vin": "VIN1", "make": "TESLA", "model": "Model Y"},  # no modelYear
        ]
    }
    result = parse_vehicles_response(api_response)
    assert result["vehicle_composition"] == [
        {"make": "TESLA", "model": "Model Y", "year": None, "count": 1}
    ]


def test_known_operators_include_tesla_be_id():
    tesla = [op for op in KNOWN_OPERATORS if op[0] == "AV8313426653583"]
    assert len(tesla) == 1
    assert tesla[0][1] == "81edcff1-8a6e-4ed0-be1f-60668515e223"
    assert "Tesla" in tesla[0][2]


def test_operator_name_terms_prefer_specific_names():
    assert "Tesla Robotaxi" in OPERATOR_NAME_TERMS
    assert "Waymo" in OPERATOR_NAME_TERMS
    # Broad LLC/Inc should not be primary name terms
    assert "LLC" not in OPERATOR_NAME_TERMS
    assert "Inc" not in OPERATOR_NAME_TERMS


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeClient:
    """Minimal httpx.Client stub for discovery helpers."""

    def __init__(self, search_results_by_query: dict):
        self.search_results_by_query = search_results_by_query
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": params or {}})
        query = (params or {}).get("searchValue", "")
        payload = self.search_results_by_query.get(
            query, {"results": [], "total": 0}
        )
        return _FakeResponse(payload)


def test_seed_from_known_operators_uses_company_name_hit():
    client = _FakeClient(
        {
            "Tesla Robotaxi": {
                "results": [
                    {
                        "businessEntityId": "81edcff1-8a6e-4ed0-be1f-60668515e223",
                        "companyName": "Tesla Robotaxi, LLC",
                        "autonomousVehicleAuthorizationNumber": "AV8313426653583",
                        "autonomousVehicleStatus": "authorized",
                    }
                ],
                "total": 1,
            }
        }
    )
    # Only exercise Tesla by temporarily filtering — call real helper with full list
    # but stub returns empty for other names so they fall back to hardcoded BE ids.
    discovered = _seed_from_known_operators(client)
    assert "AV8313426653583" in discovered
    assert (
        discovered["AV8313426653583"]["businessEntityId"]
        == "81edcff1-8a6e-4ed0-be1f-60668515e223"
    )
    assert discovered["AV8313426653583"]["autonomousVehicleStatus"] == "authorized"
    # Other seeds still present via BE-id fallback
    assert len(discovered) == len(KNOWN_OPERATORS)


def test_seed_from_known_operators_falls_back_to_be_id():
    # All company_name searches miss → every seed uses hardcoded BE id
    client = _FakeClient({})
    discovered = _seed_from_known_operators(client)
    assert len(discovered) == len(KNOWN_OPERATORS)
    tesla = discovered["AV8313426653583"]
    assert tesla["businessEntityId"] == "81edcff1-8a6e-4ed0-be1f-60668515e223"
    assert tesla["autonomousVehicleAuthorizationNumber"] == "AV8313426653583"


class _FakeVehicleClient:
    """httpx.Client stub that pages {vehicles, total} like TxMCCS (max limit 100)."""

    def __init__(self, vehicles, total=None, ignore_limit=False, page_cap=20):
        self.vehicles = vehicles
        self.total = total if total is not None else len(vehicles)
        self.ignore_limit = ignore_limit
        self.page_cap = page_cap
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        params = params or {}
        self.calls.append({"url": url, "params": dict(params)})
        if self.ignore_limit:
            return _FakeResponse({"vehicles": list(self.vehicles), "total": self.total})
        limit = int(params.get("limit", self.page_cap))
        offset = int(params.get("offset", 0))
        page = self.vehicles[offset : offset + limit]
        return _FakeResponse({"vehicles": page, "total": self.total})


def _veh(i, model="Model Y"):
    return {"vin": f"VIN{i:04d}", "make": "TESLA", "model": model, "modelYear": 2026}


def test_vehicle_page_size_is_txmccs_max():
    assert VEHICLE_PAGE_SIZE == 100


def test_fetch_all_vehicles_single_page_when_complete():
    fleet = [_veh(i) for i in range(13)]
    client = _FakeVehicleClient(fleet)
    result = fetch_all_vehicles(client, "be-tesla")
    assert result["total"] == 13
    assert len(result["vehicles"]) == 13
    assert len(client.calls) == 1
    assert client.calls[0]["params"]["limit"] == VEHICLE_PAGE_SIZE
    assert client.calls[0]["params"]["offset"] == 0
    assert "automated-motor-vehicles" in client.calls[0]["url"]


def test_fetch_all_vehicles_paginates_until_total():
    """Regression: TxMCCS default page is 20; len(vehicles) is not fleet size."""
    fleet = [_veh(i) for i in range(250)]
    client = _FakeVehicleClient(fleet, page_cap=20)
    result = fetch_all_vehicles(client, "be-tesla")
    assert result["total"] == 250
    assert len(result["vehicles"]) == 250
    assert [v["vin"] for v in result["vehicles"]] == [v["vin"] for v in fleet]
    assert len(client.calls) == 3  # 100 + 100 + 50
    assert [c["params"]["offset"] for c in client.calls] == [0, 100, 200]


def test_fetch_all_vehicles_default_page_of_20_is_not_the_count():
    fleet = [_veh(i) for i in range(432)]
    client = _FakeVehicleClient(fleet, page_cap=20)
    result = fetch_all_vehicles(client, "be-tesla")
    parsed = parse_vehicles_response(result)
    assert parsed["vehicle_count"] == 432
    assert parsed["vehicle_count"] != 20


def test_fetch_all_vehicles_unpaginated_response_does_not_refetch():
    """If the API ignores limit and returns the full list, stop after one call."""
    fleet = [_veh(i) for i in range(150)]
    client = _FakeVehicleClient(fleet, ignore_limit=True)
    result = fetch_all_vehicles(client, "be-tesla")
    assert len(result["vehicles"]) == 150
    assert len(client.calls) == 1


def test_fetch_all_vehicles_raises_when_pages_stop_short_of_total():
    fleet = [_veh(i) for i in range(40)]
    client = _FakeVehicleClient(fleet, total=432, page_cap=20)
    with pytest.raises(IncompleteVehicleList):
        fetch_all_vehicles(client, "be-tesla")
