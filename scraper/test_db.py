import os
import sqlite3
import tempfile
import pytest
from db import init_db, upsert_operator, insert_snapshot, \
    save_subscription, get_all_subscriptions, delete_subscription, \
    get_tesla_recent_snapshots

@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    yield path
    os.unlink(path)

def test_init_db_creates_tables(db_path):
    conn = sqlite3.connect(db_path)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert "operators" in tables
    assert "snapshots" in tables

def test_upsert_operator_inserts(db_path):
    upsert_operator(db_path, "AV123", "Tesla", "AV123")
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT name FROM operators WHERE id='AV123'").fetchone()
    conn.close()
    assert row[0] == "Tesla"

def test_upsert_operator_updates_name(db_path):
    upsert_operator(db_path, "AV123", "Tesla", "AV123")
    upsert_operator(db_path, "AV123", "Tesla Inc", "AV123")
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT name FROM operators WHERE id='AV123'").fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0][0] == "Tesla Inc"

def test_insert_snapshot(db_path):
    upsert_operator(db_path, "AV123", "Tesla", "AV123")
    insert_snapshot(db_path, "AV123", 42, "Model Y", "Authorized", '{"raw": true}')
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT vehicle_count FROM snapshots WHERE operator_id='AV123'").fetchone()
    conn.close()
    assert row[0] == 42

def test_push_subscriptions_table_created(db_path):
    import sqlite3
    conn = sqlite3.connect(db_path)
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    assert "push_subscriptions" in tables

def test_save_and_get_subscription(db_path):
    save_subscription(db_path, "https://push.example.com/1", "p256dh_val", "auth_val")
    subs = get_all_subscriptions(db_path)
    assert len(subs) == 1
    assert subs[0]["endpoint"] == "https://push.example.com/1"
    assert subs[0]["p256dh"] == "p256dh_val"
    assert subs[0]["auth"] == "auth_val"

def test_save_subscription_upserts(db_path):
    save_subscription(db_path, "https://push.example.com/1", "old_p256dh", "old_auth")
    save_subscription(db_path, "https://push.example.com/1", "new_p256dh", "new_auth")
    subs = get_all_subscriptions(db_path)
    assert len(subs) == 1
    assert subs[0]["p256dh"] == "new_p256dh"

def test_delete_subscription(db_path):
    save_subscription(db_path, "https://push.example.com/1", "p256dh_val", "auth_val")
    delete_subscription(db_path, "https://push.example.com/1")
    assert get_all_subscriptions(db_path) == []

def test_get_tesla_recent_snapshots(db_path):
    upsert_operator(db_path, "AV8313426653583", "Tesla", "AV8313426653583")
    insert_snapshot(db_path, "AV8313426653583", 100, "Model Y", "Authorized", "{}")
    insert_snapshot(db_path, "AV8313426653583", 110, "Model Y", "Authorized", "{}")
    snaps = get_tesla_recent_snapshots(db_path, "AV8313426653583", limit=2)
    assert len(snaps) == 2
    assert snaps[0]["vehicle_count"] == 110
    assert snaps[1]["vehicle_count"] == 100
