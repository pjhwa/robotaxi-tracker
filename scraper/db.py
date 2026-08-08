import sqlite3
from datetime import datetime, timezone
from typing import Optional


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

            -- Singleton row (id=1) tracking the latest scrape attempt.
            CREATE TABLE IF NOT EXISTS scrape_health (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                last_attempt_at TEXT,
                last_success_at TEXT,
                last_error TEXT,
                operators_ok INTEGER DEFAULT 0,
                operators_failed INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'no_data'
            );
        """)
        conn.commit()

        # Migration: add vehicle_composition column if not present
        try:
            conn.execute("ALTER TABLE snapshots ADD COLUMN vehicle_composition TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists

        # Ensure singleton row exists
        conn.execute("""
            INSERT OR IGNORE INTO scrape_health (id, status)
            VALUES (1, 'no_data')
        """)
        conn.commit()
    finally:
        conn.close()


def record_scrape_health(
    db_path: str,
    status: str,
    operators_ok: int = 0,
    operators_failed: int = 0,
    error: Optional[str] = None,
    success: bool = False,
) -> None:
    """
    Update the singleton scrape_health row.

    status: 'ok' | 'degraded' | 'failed' | 'no_data'
    success=True updates last_success_at (partial success counts).
    """
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("""
            INSERT INTO scrape_health (
                id, last_attempt_at, last_success_at, last_error,
                operators_ok, operators_failed, status
            ) VALUES (1, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                last_attempt_at = excluded.last_attempt_at,
                last_success_at = CASE
                    WHEN ? THEN excluded.last_success_at
                    ELSE scrape_health.last_success_at
                END,
                last_error = excluded.last_error,
                operators_ok = excluded.operators_ok,
                operators_failed = excluded.operators_failed,
                status = excluded.status
        """, (
            now,
            now if success else None,
            error,
            operators_ok,
            operators_failed,
            status,
            1 if success else 0,
        ))
        conn.commit()
    finally:
        conn.close()


def get_scrape_health(db_path: str) -> Optional[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT last_attempt_at, last_success_at, last_error, "
            "operators_ok, operators_failed, status "
            "FROM scrape_health WHERE id = 1"
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()
    return dict(row) if row else None


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
    vehicle_composition: str = "",
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("""
            INSERT INTO snapshots (operator_id, vehicle_count, vehicle_type, status, raw_json, vehicle_composition, captured_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (operator_id, vehicle_count, vehicle_type, status, raw_json, vehicle_composition or None, now))
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
            ORDER BY captured_at DESC, id DESC
            LIMIT ?
        """, (operator_id, limit)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]
