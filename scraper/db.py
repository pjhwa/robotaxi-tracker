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

            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint TEXT UNIQUE NOT NULL,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
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


def save_subscription(db_path: str, endpoint: str, p256dh: str, auth: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("""
            INSERT OR REPLACE INTO push_subscriptions (endpoint, p256dh, auth, created_at)
            VALUES (?, ?, ?, ?)
        """, (endpoint, p256dh, auth, now))
        conn.commit()
    finally:
        conn.close()


def get_all_subscriptions(db_path: str) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT endpoint, p256dh, auth FROM push_subscriptions"
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def delete_subscription(db_path: str, endpoint: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute(
            "DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,)
        )
        conn.commit()
    finally:
        conn.close()


def get_tesla_recent_snapshots(db_path: str, operator_id: str, limit: int = 2) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT vehicle_count, captured_at
            FROM snapshots
            WHERE operator_id = ?
            ORDER BY captured_at DESC
            LIMIT ?
        """, (operator_id, limit)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]
