# Texas Robotaxi Tracker — Design Spec
**Date:** 2026-06-05  
**Status:** Implemented (see [Amendments](#amendments) for post-launch changes)

---

## Overview

A Dockerized web dashboard that polls the Texas DMV TxMCCS public REST API every 15 minutes and displays near-real-time fleet size data for Tesla, Waymo, and other AV operators in Texas. Stores history in SQLite and presents trends via a React frontend.

---

## Architecture

Three Docker containers managed by `docker compose`:

```
scraper  →  SQLite (volume)  ←  api (FastAPI :8000)  ←  frontend (Nginx :443 → host 8443)
```

- **scraper**: Python + `httpx` + APScheduler. Polls TxMCCS JSON APIs (no browser). Writes operator snapshots and scrape health to SQLite.
- **api**: FastAPI. Read-only access to the same SQLite file; exposes REST for the frontend and push subscription endpoints.
- **frontend**: React (Vite) + Recharts, served by Nginx with TLS. Proxies `/api/*` to the API container. Auto-refreshes every 15 minutes.

All three share a named Docker volume for SQLite (`/data/robotaxi.db`).

---

## Data Model

### `operators`
| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | Authorization number, e.g. `AV8313426653583` |
| name | TEXT | Legal / company name |
| permit_number | TEXT | Same as id in practice |
| first_seen_at | TEXT | ISO timestamp |
| last_updated_at | TEXT | ISO timestamp |

### `snapshots`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | autoincrement |
| operator_id | TEXT FK | references operators.id |
| vehicle_count | INTEGER | `len(vehicles)` from TxMCCS |
| vehicle_type | TEXT | Dominant model name |
| vehicle_composition | TEXT | JSON array of `{make, model, year, count}` (nullable for old rows) |
| status | TEXT | e.g. `authorized` |
| raw_json | TEXT | Detail + vehicles payload |
| captured_at | TEXT | ISO timestamp |

Index: `(operator_id, captured_at)`.

### `scrape_health` (singleton `id = 1`)
| Column | Type | Notes |
|---|---|---|
| last_attempt_at | TEXT | Every scrape run |
| last_success_at | TEXT | Only when ≥1 operator saved |
| last_error | TEXT | Optional error summary |
| operators_ok | INTEGER | |
| operators_failed | INTEGER | |
| status | TEXT | `ok` \| `degraded` \| `failed` \| `no_data` |

### `push_subscriptions`
Web Push endpoints (`endpoint`, `p256dh`, `auth`, `created_at`). See web-push design spec.

---

## Scraper

- Language: Python 3.12
- Libraries: `httpx`, `apscheduler`, `sqlite3`, `pywebpush` (notifications)
- **API base:** `https://txmccs.txdmv.gov/api/TruckStop`
- **Discovery:**
  1. Seed authorization numbers via `searchType=autonomous_vehicle_authorization_number`
  2. Keyword search via `searchType=company_name`
- **Per operator:**  
  `GET /companies/{businessEntityId}` +  
  `GET /companies/{businessEntityId}/automated-motor-vehicles`
- Interval: 15 minutes (immediate run on startup)
- Per-operator failures are logged and counted; scheduler keeps running
- On Tesla vehicle_count change, optional Web Push to stored subscriptions

Detailed endpoint shapes: [`../../DATA_SOURCE.md`](../../DATA_SOURCE.md), [`../../../scraper/selector_findings.txt`](../../../scraper/selector_findings.txt).

---

## API Endpoints

Base URL: `http://localhost:8000` (or `/api` via frontend proxy)

| Method | Path | Description |
|---|---|---|
| GET | `/operators` | All operators + latest snapshot |
| GET | `/operators/{id}/history` | Time series (`?days=7\|30`, omit for all) |
| GET | `/snapshots/latest` | Latest snapshot per operator |
| GET | `/events/changes` | Count-change events (`?page=`) |
| GET | `/health` | Scrape health (status, ages, errors) |
| GET | `/push/vapid-public-key` | VAPID public key |
| POST | `/push/subscribe` | Register push subscription |
| DELETE | `/push/unsubscribe` | Remove push subscription |

### Health status values

`ok` | `degraded` | `stale` | `failed` | `no_data`  
Stale threshold: last success older than 45 minutes.

---

## Frontend UI

React + Vite + Recharts. Sections:

1. **Header** — Live/Degraded/Stale/Offline indicator, last update age, optional push button  
2. **Scrape warning banner** — when health status ≠ `ok`  
3. **Summary cards** — Tesla emphasized; vehicle composition breakdown on Tesla card  
4. **Tesla trend chart** — 7 / 30 / all days  
5. **Comparison chart** + other operators strip  
6. **Change event log** — paginated  

Auto-refresh: every 15 minutes (`/snapshots/latest`, history, events, `/health`).

---

## Docker Compose

```
robotaxi-tracker/
├── docker-compose.yml
├── scraper/
├── api/
├── frontend/          # host port 8443 → container 443
├── certs/             # TLS certs for nginx
└── vapid/             # private key for web push (optional)
```

- SQLite: volume mount `/data/robotaxi.db`
- Frontend nginx proxies `/api/*` → `http://api:8000/`

---

## Error Handling

- **Scraper:** exceptions per operator or whole run are logged; `scrape_health` records status; scheduler continues.
- **TxMCCS API change:** prefer updating `scraper.py` against `selector_findings.txt` / live SPA bundle; do not rely on removed `/operators/*` paths.
- **API down:** frontend shows load-error banner.
- **Stale/failed scrape with cached DB:** frontend shows health warning; numbers remain last successful snapshots until a good run.

---

## Out of Scope (original)

- Authentication / multi-user accounts
- Historical import from before first scrape
- Mobile-first redesign (desktop-oriented CSS)

*(Web Push and vehicle composition were later added — see sibling specs.)*

---

## Amendments

| Date | Change |
|------|--------|
| 2026-06-05 | Initial design: assumed Playwright/DOM scrape of TxMCCS SPA. |
| 2026-06 | Implementation used public REST API instead of Playwright (see selector findings). |
| 2026-06-09 | Web Push for Tesla count changes. |
| 2026-06-19 | `vehicle_composition` on snapshots + Tesla card breakdown. |
| **2026-07-30** | **TxMCCS broke `/operators/{id}` endpoints** (SPA HTML). Scraper saved 0 operators until fix. |
| **2026-08-08** | Scraper switched to company-centric endpoints; `scrape_health` table; `/health` expanded; UI warning banner + header status. |
