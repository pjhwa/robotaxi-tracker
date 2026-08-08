import pytest
from scraper import parse_operator_detail, parse_company, parse_vehicles_response


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
        ]
    }
    result = parse_vehicles_response(api_response)
    assert result["vehicle_count"] == 2
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
