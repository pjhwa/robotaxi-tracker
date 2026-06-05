import pytest
from scraper import parse_operator_detail, parse_vehicles_response


def test_parse_operator_detail_extracts_fields():
    api_response = {
        "operator": {
            "authorizationNumber": "AV8313426653583",
            "status": "authorized",
            "businessEntity": {
                "legalName": "Tesla Robotaxi, LLC",
            }
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
