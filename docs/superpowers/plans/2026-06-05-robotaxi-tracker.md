# Texas Robotaxi Tracker Implementation Plan

> **Historical plan (2026-06-05).** Kept for implementation history.  
> **Current system docs:** [README](../../../README.md) · [DATA_SOURCE](../../DATA_SOURCE.md) · [design spec](../specs/2026-06-05-robotaxi-tracker-design.md)  
> Scraper is **httpx + TxMCCS company REST API** (not Playwright). Frontend is **HTTPS :8443**.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Dockerized web dashboard that scrapes TxMCCS every 15 minutes and displays near-real-time Tesla/Waymo/etc fleet size trends with history.

**Architecture:** Playwright scraper writes to shared SQLite → FastAPI reads and exposes REST → React+Vite frontend served by Nginx. Three Docker containers wired by `docker compose`, sharing one named volume for the DB.

**Tech Stack:** Python 3.12, Playwright, APScheduler, FastAPI, SQLite, React 18, Vite, Recharts, Nginx, Docker Compose

---

## File Map

```
robotaxi-tracker/
├── docker-compose.yml
├── scraper/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── db.py          # schema init + write helpers
│   ├── scraper.py     # Playwright page extraction logic
│   └── main.py        # APScheduler entry point
├── api/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── db.py          # read-only DB helpers
│   ├── models.py      # Pydantic response schemas
│   └── main.py        # FastAPI app + all routes
└── frontend/
    ├── Dockerfile
    ├── nginx.conf
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── api.js
        └── components/
            ├── Header.jsx
            ├── SummaryCards.jsx
            ├── TrendChart.jsx
            ├── ComparisonChart.jsx
            └── ChangeLog.jsx
```

---

## Task 1: Project Scaffold + Docker Compose

**Files:**
- Create: `docker-compose.yml`
- Create: `scraper/requirements.txt`
- Create: `api/requirements.txt`

- [ ] **Step 1: Create `docker-compose.yml`**

```yaml
version: "3.9"

services:
  scraper:
    build: ./scraper
    volumes:
      - robotaxi_db:/data
    environment:
      - DB_PATH=/data/robotaxi.db
    restart: unless-stopped
    depends_on: []

  api:
    build: ./api
    volumes:
      - robotaxi_db:/data
    environment:
      - DB_PATH=/data/robotaxi.db
    ports:
      - "8000:8000"
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "80:80"
    depends_on:
      - api
    restart: unless-stopped

volumes:
  robotaxi_db:
```

- [ ] **Step 2: Create `scraper/requirements.txt`**

```
playwright==1.44.0
apscheduler==3.10.4
```

- [ ] **Step 3: Create `api/requirements.txt`**

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
```

- [ ] **Step 4: Commit**

```bash
git init
git add docker-compose.yml scraper/requirements.txt api/requirements.txt
git commit -m "feat: project scaffold and docker compose"
```

---

## Task 2: Database Schema (scraper)

**Files:**
- Create: `scraper/db.py`
- Create: `scraper/test_db.py`

- [ ] **Step 1: Write failing test**

Create `scraper/test_db.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd scraper && pip install pytest && python -m pytest test_db.py -v
```

Expected: `ModuleNotFoundError: No module named 'db'`

- [ ] **Step 3: Implement `scraper/db.py`**

```python
import sqlite3
from datetime import datetime, timezone


def init_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
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
    conn.close()


def upsert_operator(db_path: str, op_id: str, name: str, permit_number: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    conn.execute("""
        INSERT INTO operators (id, name, permit_number, first_seen_at, last_updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            permit_number=excluded.permit_number,
            last_updated_at=excluded.last_updated_at
    """, (op_id, name, permit_number, now, now))
    conn.commit()
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
    conn.execute("""
        INSERT INTO snapshots (operator_id, vehicle_count, vehicle_type, status, raw_json, captured_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (operator_id, vehicle_count, vehicle_type, status, raw_json, now))
    conn.commit()
    conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest test_db.py -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scraper/db.py scraper/test_db.py
git commit -m "feat: SQLite schema with operators and snapshots tables"
```

---

## Task 3: DOM Explorer (discover TxMCCS page structure)

**Files:**
- Create: `scraper/explore.py` (throwaway script, deleted after Task 4)

TxMCCS is a JS-rendered SPA. Before writing selectors, explore the actual DOM.

- [ ] **Step 1: Install Playwright and Chromium locally**

```bash
cd scraper
pip install playwright==1.44.0
playwright install chromium
```

- [ ] **Step 2: Create `scraper/explore.py`**

```python
"""Run once to inspect TxMCCS page structure. Delete after confirming selectors."""
import asyncio
from playwright.async_api import async_playwright

LIST_URL = "https://txmccs.txdmv.gov/automated-vehicles/operators"
TESLA_URL = "https://txmccs.txdmv.gov/automated-vehicles/operators/AV8313426653583"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # headed so you can see it
        page = await browser.new_page()

        print("=== OPERATOR LIST PAGE ===")
        await page.goto(LIST_URL)
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)
        content = await page.content()
        # Print first 5000 chars to find operator links/table structure
        print(content[:5000])

        print("\n=== TESLA DETAIL PAGE ===")
        await page.goto(TESLA_URL)
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)
        content = await page.content()
        print(content[:5000])

        await browser.close()

asyncio.run(main())
```

- [ ] **Step 3: Run and record findings**

```bash
cd scraper && python explore.py
```

Look for:
- On list page: what selector contains operator links? (e.g. `a[href*="/operators/AV"]`, a `<table>` row, a `<li>`)
- On detail page: what selector contains vehicle count? operator name? vehicle type? status?

Write down the selectors you find. You will use them in Task 4.

Example findings (update with actual values):
```
LIST_OPERATOR_LINKS = "a[href*='/automated-vehicles/operators/AV']"
DETAIL_VEHICLE_COUNT = "td.vehicle-count"  # <- replace with actual
DETAIL_OPERATOR_NAME = "h1.operator-name"  # <- replace with actual
DETAIL_VEHICLE_TYPE  = "td.vehicle-type"   # <- replace with actual
DETAIL_STATUS        = "span.auth-status"  # <- replace with actual
```

- [ ] **Step 4: Delete explore.py (it was throwaway)**

```bash
rm scraper/explore.py
```

---

## Task 4: Scraper Logic

**Files:**
- Create: `scraper/scraper.py`
- Create: `scraper/test_scraper.py`

Replace the placeholder selectors below with what you found in Task 3.

- [ ] **Step 1: Write failing test**

Create `scraper/test_scraper.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from scraper import parse_operator_detail


def test_parse_operator_detail_extracts_fields():
    # Simulate the dict returned by extract_page_data (Playwright result)
    page_data = {
        "name": "Tesla",
        "permit_number": "AV8313426653583",
        "vehicle_count": "42",
        "vehicle_type": "Model Y",
        "status": "Authorized",
    }
    result = parse_operator_detail(page_data)
    assert result["name"] == "Tesla"
    assert result["vehicle_count"] == 42
    assert result["vehicle_type"] == "Model Y"
    assert result["status"] == "Authorized"


def test_parse_operator_detail_handles_missing_count():
    page_data = {
        "name": "Tesla",
        "permit_number": "AV8313426653583",
        "vehicle_count": "",
        "vehicle_type": "Model Y",
        "status": "Authorized",
    }
    result = parse_operator_detail(page_data)
    assert result["vehicle_count"] == 0


def test_parse_operator_detail_strips_whitespace():
    page_data = {
        "name": "  Tesla  ",
        "permit_number": "AV8313426653583",
        "vehicle_count": " 42 ",
        "vehicle_type": " Model Y ",
        "status": " Authorized ",
    }
    result = parse_operator_detail(page_data)
    assert result["name"] == "Tesla"
    assert result["vehicle_count"] == 42
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest test_scraper.py -v
```

Expected: `ImportError: cannot import name 'parse_operator_detail' from 'scraper'`

- [ ] **Step 3: Implement `scraper/scraper.py`**

Replace `LIST_OPERATOR_LINKS`, `DETAIL_*` selectors with values from Task 3.

```python
import asyncio
import json
import logging
from typing import Optional
from playwright.async_api import async_playwright, Page

logger = logging.getLogger(__name__)

BASE_URL = "https://txmccs.txdmv.gov"
LIST_URL = f"{BASE_URL}/automated-vehicles/operators"

# Update these selectors based on Task 3 findings
LIST_OPERATOR_LINKS = "a[href*='/automated-vehicles/operators/AV']"
DETAIL_OPERATOR_NAME = "h1"           # <- update from Task 3
DETAIL_VEHICLE_COUNT = "[data-vehicle-count]"  # <- update from Task 3
DETAIL_VEHICLE_TYPE  = "[data-vehicle-type]"   # <- update from Task 3
DETAIL_STATUS        = "[data-status]"         # <- update from Task 3


def parse_operator_detail(page_data: dict) -> dict:
    """Convert raw string values from page extraction to typed dict."""
    count_raw = page_data.get("vehicle_count", "").strip()
    try:
        count = int(count_raw)
    except (ValueError, TypeError):
        count = 0
    return {
        "name": page_data.get("name", "").strip(),
        "permit_number": page_data.get("permit_number", "").strip(),
        "vehicle_count": count,
        "vehicle_type": page_data.get("vehicle_type", "").strip(),
        "status": page_data.get("status", "").strip(),
    }


async def _extract_text(page: Page, selector: str) -> str:
    try:
        el = await page.query_selector(selector)
        if el:
            return (await el.inner_text()).strip()
    except Exception as e:
        logger.warning("Selector %s failed: %s", selector, e)
    return ""


async def scrape_operator(browser, operator_id: str) -> Optional[dict]:
    """Fetch and parse one operator's detail page. Returns None on failure."""
    url = f"{BASE_URL}/automated-vehicles/operators/{operator_id}"
    page = await browser.new_page()
    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
        raw = {
            "name": await _extract_text(page, DETAIL_OPERATOR_NAME),
            "permit_number": operator_id,
            "vehicle_count": await _extract_text(page, DETAIL_VEHICLE_COUNT),
            "vehicle_type": await _extract_text(page, DETAIL_VEHICLE_TYPE),
            "status": await _extract_text(page, DETAIL_STATUS),
        }
        parsed = parse_operator_detail(raw)
        parsed["raw_json"] = json.dumps(raw)
        parsed["operator_id"] = operator_id
        return parsed
    except Exception as e:
        logger.error("Failed to scrape operator %s: %s", operator_id, e)
        return None
    finally:
        await page.close()


async def scrape_all_operators() -> list[dict]:
    """
    1. Load operator list page, collect all operator IDs from links.
    2. Scrape each operator detail page.
    Returns list of parsed operator dicts.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        list_page = await browser.new_page()

        try:
            await list_page.goto(LIST_URL, wait_until="networkidle", timeout=30000)
            links = await list_page.query_selector_all(LIST_OPERATOR_LINKS)
            hrefs = []
            for link in links:
                href = await link.get_attribute("href")
                if href:
                    hrefs.append(href)
        except Exception as e:
            logger.error("Failed to load operator list: %s", e)
            await browser.close()
            return []
        finally:
            await list_page.close()

        # Extract operator IDs from hrefs like /automated-vehicles/operators/AV123
        operator_ids = []
        for href in hrefs:
            parts = href.rstrip("/").split("/")
            op_id = parts[-1]
            if op_id.startswith("AV") and op_id not in operator_ids:
                operator_ids.append(op_id)

        logger.info("Found %d operators", len(operator_ids))

        results = []
        for op_id in operator_ids:
            result = await scrape_operator(browser, op_id)
            if result:
                results.append(result)

        await browser.close()
        return results
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest test_scraper.py -v
```

Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scraper/scraper.py scraper/test_scraper.py
git commit -m "feat: Playwright scraper with parse_operator_detail"
```

---

## Task 5: Scraper Entry Point (APScheduler)

**Files:**
- Create: `scraper/main.py`
- Create: `scraper/Dockerfile`

- [ ] **Step 1: Create `scraper/main.py`**

```python
import asyncio
import logging
import os
from apscheduler.schedulers.blocking import BlockingScheduler
from db import init_db, upsert_operator, insert_snapshot
from scraper import scrape_all_operators

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("DB_PATH", "/data/robotaxi.db")


def run_scrape():
    logger.info("Starting scrape run")
    try:
        results = asyncio.run(scrape_all_operators())
        for r in results:
            upsert_operator(DB_PATH, r["operator_id"], r["name"], r["permit_number"])
            insert_snapshot(
                DB_PATH,
                r["operator_id"],
                r["vehicle_count"],
                r["vehicle_type"],
                r["status"],
                r["raw_json"],
            )
        logger.info("Scrape complete: %d operators saved", len(results))
    except Exception as e:
        logger.error("Scrape run failed: %s", e)


if __name__ == "__main__":
    init_db(DB_PATH)
    logger.info("DB initialized at %s", DB_PATH)

    # Run once immediately on startup
    run_scrape()

    scheduler = BlockingScheduler()
    scheduler.add_job(run_scrape, "interval", minutes=15)
    logger.info("Scheduler started: every 15 minutes")
    scheduler.start()
```

- [ ] **Step 2: Create `scraper/Dockerfile`**

```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

- [ ] **Step 3: Build scraper image to verify it works**

```bash
cd scraper && docker build -t robotaxi-scraper .
```

Expected: Image builds successfully (may take a few minutes — Playwright image is ~1GB).

- [ ] **Step 4: Commit**

```bash
git add scraper/main.py scraper/Dockerfile
git commit -m "feat: scraper entry point with APScheduler 15-min interval"
```

---

## Task 6: API — DB Read Helpers + Models

**Files:**
- Create: `api/db.py`
- Create: `api/models.py`
- Create: `api/test_db.py`

- [ ] **Step 1: Write failing tests**

Create `api/test_db.py`:

```python
import os
import sqlite3
import tempfile
import pytest
import sys
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd api && pip install pytest && python -m pytest test_db.py -v
```

Expected: `ModuleNotFoundError: No module named 'api_db'`

- [ ] **Step 3: Implement `api/db.py`** (named `api_db` to avoid conflict with scraper's `db.py` when running tests cross-directory)

Create `api/api_db.py`:

```python
import sqlite3
from typing import Optional


def _conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_latest_snapshots(db_path: str) -> list[dict]:
    """Most recent snapshot per operator, joined with operator name."""
    conn = _conn(db_path)
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
    conn.close()
    return [dict(r) for r in rows]


def get_operators_with_latest(db_path: str) -> list[dict]:
    """Same as get_latest_snapshots but includes operator metadata."""
    conn = _conn(db_path)
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
    conn.close()
    return [dict(r) for r in rows]


def get_operator_history(db_path: str, operator_id: str, days: Optional[int]) -> list[dict]:
    conn = _conn(db_path)
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
    conn.close()
    return [dict(r) for r in rows]


def get_change_events(db_path: str, page: int = 1, per_page: int = 20) -> list[dict]:
    """Return snapshots where vehicle_count differs from previous snapshot for that operator."""
    conn = _conn(db_path)
    offset = (page - 1) * per_page
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
    conn.close()
    return [dict(r) for r in rows]


def get_scraper_health(db_path: str) -> dict:
    conn = _conn(db_path)
    row = conn.execute("""
        SELECT captured_at FROM snapshots ORDER BY captured_at DESC LIMIT 1
    """).fetchone()
    conn.close()
    return {"last_scrape_at": row["captured_at"] if row else None}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest test_db.py -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Create `api/models.py`**

```python
from pydantic import BaseModel
from typing import Optional


class OperatorSummary(BaseModel):
    id: str
    name: str
    permit_number: Optional[str]
    first_seen_at: Optional[str]
    vehicle_count: Optional[int]
    vehicle_type: Optional[str]
    status: Optional[str]
    captured_at: Optional[str]


class SnapshotPoint(BaseModel):
    vehicle_count: int
    vehicle_type: Optional[str]
    status: Optional[str]
    captured_at: str


class ChangeEvent(BaseModel):
    operator_id: str
    operator_name: str
    old_count: int
    new_count: int
    delta: int
    captured_at: str


class LatestSnapshot(BaseModel):
    operator_id: str
    name: str
    vehicle_count: int
    vehicle_type: Optional[str]
    status: Optional[str]
    captured_at: str


class HealthResponse(BaseModel):
    last_scrape_at: Optional[str]
    status: str
```

- [ ] **Step 6: Commit**

```bash
git add api/api_db.py api/models.py api/test_db.py
git commit -m "feat: API read helpers and Pydantic models"
```

---

## Task 7: FastAPI App

**Files:**
- Create: `api/main.py`
- Create: `api/Dockerfile`

- [ ] **Step 1: Write failing test**

Create `api/test_api.py`:

```python
import os
import sys
import tempfile
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../scraper'))
from db import init_db, upsert_operator, insert_snapshot

os.environ["DB_PATH"] = ""  # will be set per test via monkeypatch

from fastapi.testclient import TestClient

@pytest.fixture
def client(monkeypatch, tmp_path):
    db = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db)
    init_db(db)
    upsert_operator(db, "AV001", "Tesla", "AV001")
    insert_snapshot(db, "AV001", 42, "Model Y", "Authorized", "{}")

    # Re-import after env is set
    import importlib
    import api.main as app_module
    importlib.reload(app_module)
    from api.main import app
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
    assert "last_scrape_at" in r.json()

def test_get_changes(client):
    r = client.get("/events/changes")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd api && python -m pytest test_api.py -v
```

Expected: `ModuleNotFoundError: No module named 'api.main'`

- [ ] **Step 3: Implement `api/main.py`**

```python
import os
from typing import Optional
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from models import OperatorSummary, SnapshotPoint, ChangeEvent, LatestSnapshot, HealthResponse
from api_db import (
    get_operators_with_latest,
    get_operator_history,
    get_latest_snapshots,
    get_change_events,
    get_scraper_health,
)

DB_PATH = os.environ.get("DB_PATH", "/data/robotaxi.db")

app = FastAPI(title="Robotaxi Tracker API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/operators", response_model=list[OperatorSummary])
def list_operators():
    return get_operators_with_latest(DB_PATH)


@app.get("/operators/{operator_id}/history", response_model=list[SnapshotPoint])
def operator_history(
    operator_id: str,
    days: Optional[int] = Query(None, description="7, 30, or omit for all"),
):
    return get_operator_history(DB_PATH, operator_id, days)


@app.get("/snapshots/latest", response_model=list[LatestSnapshot])
def latest_snapshots():
    return get_latest_snapshots(DB_PATH)


@app.get("/events/changes", response_model=list[ChangeEvent])
def change_events(page: int = Query(1, ge=1)):
    return get_change_events(DB_PATH, page=page)


@app.get("/health", response_model=HealthResponse)
def health():
    data = get_scraper_health(DB_PATH)
    status = "ok" if data["last_scrape_at"] else "no_data"
    return {**data, "status": status}
```

- [ ] **Step 4: Create `api/Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pip install fastapi uvicorn httpx && python -m pytest test_api.py -v
```

Expected: 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add api/main.py api/Dockerfile api/test_api.py
git commit -m "feat: FastAPI app with all 5 endpoints"
```

---

## Task 8: React Frontend Scaffold

**Files:**
- Create: `frontend/` (Vite project)
- Create: `frontend/src/api.js`

- [ ] **Step 1: Scaffold Vite + React project**

```bash
cd frontend
npm create vite@latest . -- --template react
npm install
npm install recharts
```

- [ ] **Step 2: Install dependencies and verify dev server starts**

```bash
npm run dev
```

Expected: Dev server running at `http://localhost:5173`. Open in browser — should show default Vite+React page. Stop with Ctrl+C.

- [ ] **Step 3: Clean up default boilerplate**

Replace `src/App.jsx` contents with:

```jsx
export default function App() {
  return <div>loading...</div>
}
```

Replace `src/App.css` with empty file. Remove `src/assets/react.svg` and `public/vite.svg`.

- [ ] **Step 4: Create `frontend/src/api.js`**

```js
const BASE = "/api";

export async function fetchLatestSnapshots() {
  const r = await fetch(`${BASE}/snapshots/latest`);
  if (!r.ok) throw new Error("Failed to fetch snapshots");
  return r.json();
}

export async function fetchOperators() {
  const r = await fetch(`${BASE}/operators`);
  if (!r.ok) throw new Error("Failed to fetch operators");
  return r.json();
}

export async function fetchOperatorHistory(operatorId, days) {
  const params = days ? `?days=${days}` : "";
  const r = await fetch(`${BASE}/operators/${operatorId}/history${params}`);
  if (!r.ok) throw new Error("Failed to fetch history");
  return r.json();
}

export async function fetchChangeEvents(page = 1) {
  const r = await fetch(`${BASE}/events/changes?page=${page}`);
  if (!r.ok) throw new Error("Failed to fetch events");
  return r.json();
}
```

- [ ] **Step 5: Create `frontend/vite.config.js`** (proxy `/api` → FastAPI in dev)

```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
```

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "feat: Vite+React scaffold with API client and dev proxy"
```

---

## Task 9: Summary Cards Component

**Files:**
- Create: `frontend/src/components/SummaryCards.jsx`

- [ ] **Step 1: Create `frontend/src/components/SummaryCards.jsx`**

```jsx
export default function SummaryCards({ snapshots }) {
  return (
    <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 24 }}>
      {snapshots.map((s) => (
        <Card key={s.operator_id} snapshot={s} />
      ))}
    </div>
  );
}

function Card({ snapshot }) {
  const { name, vehicle_count, captured_at } = snapshot;
  return (
    <div style={{
      background: "#1a1a2e",
      border: "1px solid #333",
      borderRadius: 8,
      padding: "16px 24px",
      minWidth: 160,
    }}>
      <div style={{ color: "#888", fontSize: 12, marginBottom: 4 }}>{name}</div>
      <div style={{ color: "#fff", fontSize: 36, fontWeight: "bold", lineHeight: 1 }}>
        {vehicle_count ?? "—"}
      </div>
      <div style={{ color: "#555", fontSize: 11, marginTop: 4 }}>
        {captured_at ? new Date(captured_at).toLocaleString("ko-KR") : ""}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Smoke-test in browser**

Temporarily add to `App.jsx`:
```jsx
import SummaryCards from './components/SummaryCards'
const mock = [
  { operator_id: "AV001", name: "Tesla", vehicle_count: 42, captured_at: new Date().toISOString() },
  { operator_id: "AV002", name: "Waymo", vehicle_count: 577, captured_at: new Date().toISOString() },
]
export default function App() {
  return <div style={{ background: "#0d0d1a", minHeight: "100vh", padding: 24 }}><SummaryCards snapshots={mock} /></div>
}
```

Run `npm run dev` and verify two cards appear with correct numbers.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SummaryCards.jsx
git commit -m "feat: SummaryCards component"
```

---

## Task 10: Trend Chart Component (Tesla history)

**Files:**
- Create: `frontend/src/components/TrendChart.jsx`

- [ ] **Step 1: Create `frontend/src/components/TrendChart.jsx`**

```jsx
import { useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";

const PERIODS = [
  { label: "7일", value: 7 },
  { label: "30일", value: 30 },
  { label: "전체", value: null },
];

export default function TrendChart({ history, onPeriodChange, period }) {
  const data = history.map((h) => ({
    time: new Date(h.captured_at).toLocaleDateString("ko-KR"),
    count: h.vehicle_count,
  }));

  return (
    <div style={{ background: "#1a1a2e", border: "1px solid #333", borderRadius: 8, padding: 24, marginBottom: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h2 style={{ color: "#fff", margin: 0, fontSize: 16 }}>Tesla 차량 수 변화</h2>
        <div style={{ display: "flex", gap: 8 }}>
          {PERIODS.map((p) => (
            <button
              key={p.label}
              onClick={() => onPeriodChange(p.value)}
              style={{
                background: period === p.value ? "#e82127" : "#333",
                color: "#fff",
                border: "none",
                borderRadius: 4,
                padding: "4px 12px",
                cursor: "pointer",
                fontSize: 12,
              }}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" />
          <XAxis dataKey="time" stroke="#555" tick={{ fontSize: 11 }} />
          <YAxis stroke="#555" tick={{ fontSize: 11 }} />
          <Tooltip
            contentStyle={{ background: "#1a1a2e", border: "1px solid #555", color: "#fff" }}
          />
          <Line type="monotone" dataKey="count" stroke="#e82127" dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/TrendChart.jsx
git commit -m "feat: TrendChart with period selector"
```

---

## Task 11: Comparison Bar Chart Component

**Files:**
- Create: `frontend/src/components/ComparisonChart.jsx`

- [ ] **Step 1: Create `frontend/src/components/ComparisonChart.jsx`**

```jsx
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  LabelList, ResponsiveContainer,
} from "recharts";

export default function ComparisonChart({ snapshots }) {
  const data = [...snapshots]
    .sort((a, b) => (b.vehicle_count ?? 0) - (a.vehicle_count ?? 0))
    .map((s) => ({ name: s.name, count: s.vehicle_count ?? 0 }));

  return (
    <div style={{ background: "#1a1a2e", border: "1px solid #333", borderRadius: 8, padding: 24, marginBottom: 24 }}>
      <h2 style={{ color: "#fff", margin: "0 0 16px", fontSize: 16 }}>운영사 비교 (현재)</h2>
      <ResponsiveContainer width="100%" height={data.length * 44 + 20}>
        <BarChart data={data} layout="vertical" margin={{ left: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" horizontal={false} />
          <XAxis type="number" stroke="#555" tick={{ fontSize: 11 }} />
          <YAxis type="category" dataKey="name" stroke="#555" tick={{ fontSize: 12 }} width={56} />
          <Tooltip
            contentStyle={{ background: "#1a1a2e", border: "1px solid #555", color: "#fff" }}
          />
          <Bar dataKey="count" fill="#00d4aa" radius={[0, 4, 4, 0]}>
            <LabelList dataKey="count" position="right" style={{ fill: "#aaa", fontSize: 12 }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ComparisonChart.jsx
git commit -m "feat: ComparisonChart horizontal bar chart"
```

---

## Task 12: Change Event Log Component

**Files:**
- Create: `frontend/src/components/ChangeLog.jsx`

- [ ] **Step 1: Create `frontend/src/components/ChangeLog.jsx`**

```jsx
import { useState } from "react";

export default function ChangeLog({ events, onPageChange, page }) {
  return (
    <div style={{ background: "#1a1a2e", border: "1px solid #333", borderRadius: 8, padding: 24, marginBottom: 24 }}>
      <h2 style={{ color: "#fff", margin: "0 0 16px", fontSize: 16 }}>변경 이벤트 로그</h2>
      {events.length === 0 ? (
        <p style={{ color: "#555" }}>아직 변경 이벤트가 없습니다.</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ color: "#666", borderBottom: "1px solid #333" }}>
              <th style={{ textAlign: "left", padding: "4px 8px" }}>시간</th>
              <th style={{ textAlign: "left", padding: "4px 8px" }}>운영사</th>
              <th style={{ textAlign: "right", padding: "4px 8px" }}>변화</th>
              <th style={{ textAlign: "right", padding: "4px 8px" }}>증감</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e, i) => (
              <tr key={i} style={{ borderBottom: "1px solid #222", color: "#ccc" }}>
                <td style={{ padding: "6px 8px" }}>
                  {new Date(e.captured_at).toLocaleString("ko-KR")}
                </td>
                <td style={{ padding: "6px 8px" }}>{e.operator_name}</td>
                <td style={{ padding: "6px 8px", textAlign: "right" }}>
                  {e.old_count} → {e.new_count}
                </td>
                <td style={{
                  padding: "6px 8px", textAlign: "right",
                  color: e.delta > 0 ? "#00d4aa" : "#e82127",
                }}>
                  {e.delta > 0 ? `+${e.delta}` : e.delta}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div style={{ display: "flex", gap: 8, marginTop: 12, justifyContent: "flex-end" }}>
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          style={{ background: "#333", color: "#fff", border: "none", borderRadius: 4, padding: "4px 10px", cursor: "pointer" }}
        >
          ←
        </button>
        <span style={{ color: "#666", fontSize: 12, lineHeight: "26px" }}>p.{page}</span>
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={events.length < 20}
          style={{ background: "#333", color: "#fff", border: "none", borderRadius: 4, padding: "4px 10px", cursor: "pointer" }}
        >
          →
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ChangeLog.jsx
git commit -m "feat: ChangeLog table with pagination"
```

---

## Task 13: Header Component + App Wiring

**Files:**
- Create: `frontend/src/components/Header.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/main.jsx`

- [ ] **Step 1: Create `frontend/src/components/Header.jsx`**

```jsx
export default function Header({ lastUpdated }) {
  const ago = lastUpdated
    ? Math.round((Date.now() - new Date(lastUpdated).getTime()) / 60000)
    : null;

  return (
    <header style={{
      display: "flex", justifyContent: "space-between", alignItems: "center",
      padding: "16px 24px", borderBottom: "1px solid #222", marginBottom: 24,
    }}>
      <h1 style={{ color: "#fff", margin: 0, fontSize: 20 }}>
        🚖 Texas Robotaxi Tracker
      </h1>
      <span style={{ color: "#555", fontSize: 12 }}>
        {ago !== null ? `Last updated: ${ago}분 전` : "데이터 없음"}
      </span>
    </header>
  );
}
```

- [ ] **Step 2: Rewrite `frontend/src/App.jsx`**

```jsx
import { useState, useEffect, useCallback } from "react";
import Header from "./components/Header";
import SummaryCards from "./components/SummaryCards";
import TrendChart from "./components/TrendChart";
import ComparisonChart from "./components/ComparisonChart";
import ChangeLog from "./components/ChangeLog";
import {
  fetchLatestSnapshots,
  fetchOperatorHistory,
  fetchChangeEvents,
} from "./api";

const TESLA_PERMIT = "AV8313426653583";
const REFRESH_MS = 15 * 60 * 1000;

export default function App() {
  const [snapshots, setSnapshots] = useState([]);
  const [history, setHistory] = useState([]);
  const [events, setEvents] = useState([]);
  const [period, setPeriod] = useState(30);
  const [eventsPage, setEventsPage] = useState(1);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [error, setError] = useState(null);

  const loadAll = useCallback(async () => {
    try {
      const [snaps, hist, evts] = await Promise.all([
        fetchLatestSnapshots(),
        fetchOperatorHistory(TESLA_PERMIT, period),
        fetchChangeEvents(eventsPage),
      ]);
      setSnapshots(snaps);
      setHistory(hist);
      setEvents(evts);
      setLastUpdated(new Date().toISOString());
      setError(null);
    } catch (e) {
      setError("데이터 로딩 실패: " + e.message);
    }
  }, [period, eventsPage]);

  useEffect(() => {
    loadAll();
    const id = setInterval(loadAll, REFRESH_MS);
    return () => clearInterval(id);
  }, [loadAll]);

  const handlePeriodChange = (p) => { setPeriod(p); };
  const handlePageChange = (p) => { setEventsPage(Math.max(1, p)); };

  return (
    <div style={{ background: "#0d0d1a", minHeight: "100vh", color: "#fff", fontFamily: "system-ui, sans-serif" }}>
      <Header lastUpdated={lastUpdated} />
      <main style={{ maxWidth: 1100, margin: "0 auto", padding: "0 24px 48px" }}>
        {error && (
          <div style={{ background: "#3a1a1a", border: "1px solid #e82127", borderRadius: 6, padding: "10px 16px", marginBottom: 16, color: "#e82127" }}>
            {error}
          </div>
        )}
        <SummaryCards snapshots={snapshots} />
        <TrendChart history={history} period={period} onPeriodChange={handlePeriodChange} />
        <ComparisonChart snapshots={snapshots} />
        <ChangeLog events={events} page={eventsPage} onPageChange={handlePageChange} />
      </main>
    </div>
  );
}
```

- [ ] **Step 3: Update `frontend/src/main.jsx`** to remove StrictMode default styles

```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'

ReactDOM.createRoot(document.getElementById('root')).render(<App />)
```

- [ ] **Step 4: Run dev server and verify UI (with API running)**

Start FastAPI in one terminal:
```bash
cd api && DB_PATH=/tmp/test.db uvicorn main:app --reload
```

Start frontend in another:
```bash
cd frontend && npm run dev
```

Open `http://localhost:5173`. Expected: dark dashboard with empty cards (no data yet). No console errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/
git commit -m "feat: App wiring with auto-refresh, Header, and all four dashboard sections"
```

---

## Task 14: Frontend Docker + Nginx

**Files:**
- Create: `frontend/Dockerfile`
- Create: `frontend/nginx.conf`

- [ ] **Step 1: Create `frontend/nginx.conf`**

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    # Proxy API calls to FastAPI container
    location /api/ {
        proxy_pass http://api:8000/;
        proxy_set_header Host $host;
    }

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 2: Create `frontend/Dockerfile`**

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

- [ ] **Step 3: Build frontend image to verify**

```bash
cd frontend && docker build -t robotaxi-frontend .
```

Expected: Image builds successfully.

- [ ] **Step 4: Commit**

```bash
git add frontend/Dockerfile frontend/nginx.conf
git commit -m "feat: frontend Dockerfile with multi-stage build and Nginx proxy"
```

---

## Task 15: End-to-End Smoke Test

- [ ] **Step 1: Start everything with docker compose**

```bash
docker compose up --build
```

Wait for all three containers to start. Expected output includes:
- `scraper-1  | DB initialized at /data/robotaxi.db`
- `scraper-1  | Starting scrape run`
- `api-1      | Application startup complete`
- `frontend-1 | nginx: ready`

- [ ] **Step 2: Verify scraper writes data**

```bash
docker compose logs scraper --tail=20
```

Expected: `Scrape complete: N operators saved` (N ≥ 1)

- [ ] **Step 3: Verify API returns data**

```bash
curl http://localhost:8000/operators | python3 -m json.tool
```

Expected: JSON array with operator objects including `vehicle_count`.

```bash
curl http://localhost:8000/health | python3 -m json.tool
```

Expected: `{"last_scrape_at": "...", "status": "ok"}`

- [ ] **Step 4: Verify frontend dashboard**

Open `http://localhost:80` in browser.

Expected:
- Summary cards show operators with vehicle counts
- Tesla trend chart renders (may show single point if first run)
- Comparison bar chart shows all operators sorted by count
- Change log shows empty (expected on first run)

- [ ] **Step 5: Final commit + tag**

```bash
git add .
git commit -m "chore: end-to-end verified"
git tag v0.1.0
```

---

## Self-Review Checklist

- [x] **Spec coverage**: scraper (Task 3-5), DB schema (Task 2), all 5 API endpoints (Task 6-7), 4 UI sections (Task 9-13), Docker Compose (Task 1, 14-15), error handling (scraper try/except, frontend error banner), 15-min polling (scraper APScheduler + frontend setInterval)
- [x] **No placeholders**: all code blocks are complete; Task 3 DOM explorer explicitly handles unknown selectors
- [x] **Type consistency**: `operator_id` used consistently across `api_db.py`, `models.py`, and React components; `vehicle_count` is always `int` after `parse_operator_detail`
