import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../scraper'))
from db import init_db, upsert_operator, insert_snapshot

sys.path.insert(0, os.path.dirname(__file__))

@pytest.fixture
def client(monkeypatch, tmp_path):
    db = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db)
    init_db(db)
    upsert_operator(db, "AV001", "Tesla", "AV001")
    insert_snapshot(db, "AV001", 42, "Model Y", "Authorized", "{}")

    import importlib
    import api_db
    import main as app_module
    importlib.reload(api_db)
    importlib.reload(app_module)

    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)

def test_get_operators(client):
    r = client.get("/operators")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["name"] == "Tesla"

def test_get_operator_history(client):
    r = client.get("/operators/AV001/history?days=7")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["vehicle_count"] == 42

def test_get_snapshots_latest(client):
    r = client.get("/snapshots/latest")
    assert r.status_code == 200
    data = r.json()
    assert data[0]["vehicle_count"] == 42

def test_get_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert "last_scrape_at" in body
    assert body["status"] == "ok"

def test_get_changes(client):
    r = client.get("/events/changes")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
