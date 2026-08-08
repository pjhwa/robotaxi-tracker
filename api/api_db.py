import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional


def _parse_composition(row: dict) -> dict:
    """JSON string → list for vehicle_composition field."""
    raw = row.get("vehicle_composition")
    if raw:
        try:
            row["vehicle_composition"] = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            row["vehicle_composition"] = None
    else:
        row["vehicle_composition"] = None
    return row


def _conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_latest_snapshots(db_path: str) -> list[dict]:
    """Most recent snapshot per operator, joined with operator name."""
    conn = _conn(db_path)
    try:
        rows = conn.execute("""
            SELECT s.operator_id, o.name, s.vehicle_count, s.vehicle_type,
                   s.vehicle_composition, s.status, s.captured_at
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
    return [_parse_composition(dict(r)) for r in rows]


def get_operators_with_latest(db_path: str) -> list[dict]:
    """All operators with their latest snapshot data."""
    conn = _conn(db_path)
    try:
        rows = conn.execute("""
            SELECT o.id, o.name, o.permit_number, o.first_seen_at,
                   s.vehicle_count, s.vehicle_type, s.vehicle_composition, s.status, s.captured_at
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
    return [_parse_composition(dict(r)) for r in rows]


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


# Data older than this is considered stale (3 scrape intervals of 15 min)
STALE_AFTER_SECONDS = 45 * 60


def get_scraper_health(db_path: str) -> dict:
    """
    Return scraper health including scrape_health row (if present) and
    snapshot age. Status priority: no_data < failed < stale < degraded < ok
    (worst applicable status wins for UI warnings).
    """
    conn = _conn(db_path)
    try:
        snap = conn.execute("""
            SELECT captured_at FROM snapshots ORDER BY captured_at DESC LIMIT 1
        """).fetchone()
        try:
            health = conn.execute("""
                SELECT last_attempt_at, last_success_at, last_error,
                       operators_ok, operators_failed, status
                FROM scrape_health WHERE id = 1
            """).fetchone()
        except sqlite3.OperationalError:
            health = None
    finally:
        conn.close()

    last_snapshot = snap["captured_at"] if snap else None
    last_success = None
    last_attempt = None
    last_error = None
    operators_ok = None
    operators_failed = None
    run_status = None

    if health:
        last_success = health["last_success_at"]
        last_attempt = health["last_attempt_at"]
        last_error = health["last_error"]
        operators_ok = health["operators_ok"]
        operators_failed = health["operators_failed"]
        run_status = health["status"]

    # Prefer scrape_health success time; fall back to latest snapshot
    effective_success = last_success or last_snapshot

    data_age_seconds = None
    stale = False
    if effective_success:
        try:
            # Support both with and without timezone suffix
            ts = effective_success.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            data_age_seconds = int((datetime.now(timezone.utc) - dt).total_seconds())
            stale = data_age_seconds > STALE_AFTER_SECONDS
        except (ValueError, TypeError):
            pass

    if not effective_success and not last_attempt:
        status = "no_data"
    elif run_status == "failed" or (operators_ok == 0 and last_attempt and not last_success):
        status = "failed"
    elif stale:
        status = "stale"
    elif run_status == "degraded":
        status = "degraded"
    elif run_status == "ok" or effective_success:
        status = "ok"
    else:
        status = "no_data"

    return {
        "last_scrape_at": effective_success,
        "last_attempt_at": last_attempt,
        "last_success_at": last_success or last_snapshot,
        "last_error": last_error,
        "operators_ok": operators_ok,
        "operators_failed": operators_failed,
        "data_age_seconds": data_age_seconds,
        "stale": stale,
        "status": status,
    }


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
