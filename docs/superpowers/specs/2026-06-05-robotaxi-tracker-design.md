# Texas Robotaxi Tracker — Design Spec
**Date:** 2026-06-05  
**Status:** Approved

---

## Overview

A Dockerized web dashboard that scrapes the Texas DMV's TxMCCS automated vehicle operator registry every 15 minutes and displays near-real-time fleet size data for Tesla, Waymo, and other AV operators in Texas. Stores unlimited history in SQLite and presents trends via a React frontend.

---

## Architecture

Three Docker containers managed by `docker compose`:

```
scraper  →  SQLite (volume)  ←  api (FastAPI :8000)  ←  frontend (Nginx :80)
```

- **scraper**: Playwright-based Python service. Runs on a 15-minute cron loop. Headless Chromium renders the JS-heavy TxMCCS SPA, extracts fleet data for all operators, and writes snapshots to SQLite.
- **api**: FastAPI service. Reads from SQLite and exposes REST endpoints for the frontend. Read-only access to DB.
- **frontend**: React app built with Vite, served by Nginx. Fetches data from the API on load and auto-refreshes every 15 minutes.

All three share a single named Docker volume for the SQLite database file.

---

## Data Model

### `operators` table
Tracks known AV operators.

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | e.g. `AV8313426653583` |
| name | TEXT | e.g. `Tesla` |
| permit_number | TEXT | TxMCCS permit ID |
| first_seen_at | DATETIME | First time scraped |
| last_updated_at | DATETIME | Last snapshot time |

### `snapshots` table
One row per operator per scrape run.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | autoincrement |
| operator_id | TEXT FK | references operators.id |
| vehicle_count | INTEGER | Total registered vehicles |
| vehicle_type | TEXT | e.g. `Model Y` |
| status | TEXT | Authorization status |
| raw_json | TEXT | Full page data as JSON |
| captured_at | DATETIME | Timestamp of scrape |

Indexes: `(operator_id, captured_at)` for efficient time-series queries.

---

## Scraper

- Language: Python 3.12
- Libraries: `playwright`, `apscheduler`, `sqlite3`
- Target URL: `https://txmccs.txdmv.gov/automated-vehicles/operators`
- Scrapes the operator list page to discover all operators, then fetches each operator detail page (e.g. `/operators/AV8313426653583`)
- Runs on 15-minute intervals via APScheduler
- On first run, seeds the `operators` table
- On each run, inserts a new row into `snapshots` for every operator
- Error handling: if a page fails to load, logs the error and skips that operator (does not crash the scheduler)

---

## API Endpoints

Base URL: `http://localhost:8000`

| Method | Path | Description |
|---|---|---|
| GET | `/operators` | List all operators with latest vehicle count |
| GET | `/operators/{id}/history` | Time-series snapshots for one operator. Query params: `?days=7\|30\|all` |
| GET | `/snapshots/latest` | Most recent snapshot for all operators |
| GET | `/events/changes` | Rows where vehicle_count changed vs previous snapshot |
| GET | `/health` | Scraper last-run timestamp and status |

---

## Frontend UI

Built with React + Vite + Recharts. Single-page app with four sections:

### 1. Summary Cards (top row)
One card per operator showing:
- Operator name
- Current vehicle count (large number)
- Delta since yesterday (e.g. `▲ +1 오늘`)

### 2. Tesla Trend Chart
Line chart of Tesla's vehicle count over time.
- Period selector: 7일 / 30일 / 전체
- X-axis: date, Y-axis: vehicle count
- Rendered with Recharts `LineChart`

### 3. Operator Comparison Bar Chart
Horizontal bar chart of all operators at current snapshot.
- Sorted descending by vehicle count
- Shows operator name + count label

### 4. Change Event Log (bottom)
Table of scrape events where `vehicle_count` changed vs the previous snapshot.
- Columns: timestamp, operator, old count → new count, delta
- Most recent first, paginated (20 rows per page)

### Auto-refresh
Frontend polls `/snapshots/latest` every 15 minutes and updates all sections. Shows "Last updated: N분 전" in the header.

---

## Docker Compose Structure

```
robotaxi-tracker/
├── docker-compose.yml
├── scraper/
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── api/
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
└── frontend/
    ├── Dockerfile
    ├── nginx.conf
    └── src/
```

- `docker compose up` starts all three services
- SQLite file lives at `/data/robotaxi.db` in a named volume
- Frontend Nginx proxies `/api/*` to the FastAPI container (avoids CORS issues)

---

## Error Handling

- **Scraper failure**: APScheduler catches exceptions, logs them, and retries on next interval. Does not crash the container.
- **TxMCCS page change**: If expected DOM selectors are not found, scraper logs a warning with the raw HTML snippet for debugging.
- **API errors**: FastAPI returns standard HTTP error responses. Frontend shows a "데이터 로딩 실패" banner if API is unreachable.

---

## Out of Scope

- Authentication / login wall
- Push notifications / alerts
- Historical data import (starts from zero on first run)
- Mobile-responsive design (desktop-first)
