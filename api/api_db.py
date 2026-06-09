import sqlite3
from datetime import datetime, timezone
from typing import Optional


def _conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_latest_snapshots(db_path: str) -> list[dict]:
    """Most recent snapshot per operator, joined with operator name."""
    conn = _conn(db_path)
    try:
        rows = conn.execute("""
            SELECT s.operator_id, o.name, s.vehicle_count, s.vehicle_type, s.status, s.captured_at
            FROM snapshots s
            JOIN operators o ON o.id = s.operator_id
            WHERE s.id = (
                SELECT id FROM snapshots s2
                WHERE s2.operator_id = s.operator_id
                ORDER BY captured_at DESC LIMIT 1
            )
            ORDER BY s.vehicle_count DESC
        """).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def get_operators_with_latest(db_path: str) -> list[dict]:
    """All operators with their latest snapshot data."""
    conn = _conn(db_path)
    try:
        rows = conn.execute("""
            SELECT o.id, o.name, o.permit_number, o.first_seen_at,
                   s.vehicle_count, s.vehicle_type, s.status, s.captured_at
            FROM operators o
            LEFT JOIN snapshots s ON s.id = (
                SELECT id FROM snapshots s2
                WHERE s2.operator_id = o.id
                ORDER BY captured_at DESC LIMIT 1
            )
            ORDER BY s.vehicle_count DESC NULLS LAST
        """).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def get_operator_history(db_path: str, operator_id: str, days: Optional[int]) -> list[dict]:
    conn = _conn(db_path)
    try:
        if days is None:
            rows = conn.execute("""
                SELECT vehicle_count, vehicle_type, status, captured_at
                FROM snapshots
                WHERE operator_id = ?
                ORDER BY captured_at ASC
            """, (operator_id,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT vehicle_count, vehicle_type, status, captured_at
                FROM snapshots
                WHERE operator_id = ?
                  AND captured_at >= datetime('now', ? || ' days')
                ORDER BY captured_at ASC
            """, (operator_id, f"-{days}")).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def get_change_events(db_path: str, page: int = 1, per_page: int = 20) -> list[dict]:
    """Return snapshots where vehicle_count differs from the previous snapshot."""
    conn = _conn(db_path)
    offset = (page - 1) * per_page
    try:
        rows = conn.execute("""
            SELECT
                s.operator_id,
                o.name AS operator_name,
                prev.vehicle_count AS old_count,
                s.vehicle_count AS new_count,
                s.vehicle_count - prev.vehicle_count AS delta,
                s.captured_at
            FROM snapshots s
            JOIN operators o ON o.id = s.operator_id
            JOIN snapshots prev ON prev.id = (
                SELECT id FROM snapshots s2
                WHERE s2.operator_id = s.operator_id
                  AND s2.captured_at < s.captured_at
                ORDER BY captured_at DESC LIMIT 1
            )
            WHERE s.vehicle_count != prev.vehicle_count
            ORDER BY s.captured_at DESC
            LIMIT ? OFFSET ?
        """, (per_page, offset)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def get_scraper_health(db_path: str) -> dict:
    conn = _conn(db_path)
    try:
        row = conn.execute("""
            SELECT captured_at FROM snapshots ORDER BY captured_at DESC LIMIT 1
        """).fetchone()
    finally:
        conn.close()
    return {"last_scrape_at": row["captured_at"] if row else None}


def save_push_subscription(db_path: str, endpoint: str, p256dh: str, auth: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = _conn(db_path)
    try:
        conn.execute("""
            INSERT OR REPLACE INTO push_subscriptions (endpoint, p256dh, auth, created_at)
            VALUES (?, ?, ?, ?)
        """, (endpoint, p256dh, auth, now))
        conn.commit()
    finally:
        conn.close()


def delete_push_subscription(db_path: str, endpoint: str) -> None:
    conn = _conn(db_path)
    try:
        conn.execute(
            "DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,)
        )
        conn.commit()
    finally:
        conn.close()
