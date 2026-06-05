import os
import sqlite3
import tempfile
import pytest
from db import init_db, upsert_operator, insert_snapshot

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
