import os
import sys
import tempfile
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../scraper'))
from db import init_db, upsert_operator, insert_snapshot

sys.path.insert(0, os.path.dirname(__file__))
from api_db import get_latest_snapshots, get_operator_history, get_change_events

@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    upsert_operator(path, "AV001", "Tesla", "AV001")
    upsert_operator(path, "AV002", "Waymo", "AV002")
    insert_snapshot(path, "AV001", 40, "Model Y", "Authorized", "{}")
    insert_snapshot(path, "AV001", 42, "Model Y", "Authorized", "{}")
    insert_snapshot(path, "AV002", 577, "Jaguar I-PACE", "Authorized", "{}")
    yield path
    os.unlink(path)

def test_get_latest_snapshots_returns_one_per_operator(db_path):
    rows = get_latest_snapshots(db_path)
    assert len(rows) == 2
    tesla = next(r for r in rows if r["operator_id"] == "AV001")
    assert tesla["vehicle_count"] == 42

def test_get_operator_history_returns_all_snapshots(db_path):
    rows = get_operator_history(db_path, "AV001", days=None)
    assert len(rows) == 2

def test_get_operator_history_filters_by_days(db_path):
    rows = get_operator_history(db_path, "AV001", days=7)
    assert len(rows) == 2  # both within 7 days

def test_get_change_events_detects_count_change(db_path):
    events = get_change_events(db_path)
    tesla_events = [e for e in events if e["operator_id"] == "AV001"]
    assert len(tesla_events) == 1
    assert tesla_events[0]["old_count"] == 40
    assert tesla_events[0]["new_count"] == 42
