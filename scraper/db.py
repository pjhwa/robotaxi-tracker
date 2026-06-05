import sqlite3
from datetime import datetime, timezone


def init_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS operators (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                permit_number TEXT,
                first_seen_at TEXT NOT NULL,
                last_updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operator_id TEXT NOT NULL REFERENCES operators(id),
                vehicle_count INTEGER NOT NULL,
                vehicle_type TEXT,
                status TEXT,
                raw_json TEXT,
                captured_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_snapshots_operator_time
                ON snapshots (operator_id, captured_at);
        """)
        conn.commit()
    finally:
        conn.close()


def upsert_operator(db_path: str, op_id: str, name: str, permit_number: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("""
            INSERT INTO operators (id, name, permit_number, first_seen_at, last_updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                permit_number=excluded.permit_number,
                last_updated_at=excluded.last_updated_at
        """, (op_id, name, permit_number, now, now))
        conn.commit()
    finally:
        conn.close()


def insert_snapshot(
    db_path: str,
    operator_id: str,
    vehicle_count: int,
    vehicle_type: str,
    status: str,
    raw_json: str,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("""
            INSERT INTO snapshots (operator_id, vehicle_count, vehicle_type, status, raw_json, captured_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (operator_id, vehicle_count, vehicle_type, status, raw_json, now))
        conn.commit()
    finally:
        conn.close()
