# Data Source & Operational Notes

**Last updated:** 2026-09-01

## TxMCCS public API

The tracker does **not** scrape the DOM. It calls the same JSON APIs the TxMCCS React SPA uses.

- **Site:** https://www.txmccs.com/
- **API host:** `https://txmccs.txdmv.gov`
- **Base path:** `/api/TruckStop`
- **Auth:** none for read endpoints used by this project

### Endpoints (current)

| Purpose | Method / path |
|---------|----------------|
| Company search | `GET /companies?searchType={type}&searchValue={q}` |
| Company detail | `GET /companies/{businessEntityId}` |
| AV vehicle list | `GET /companies/{businessEntityId}/automated-motor-vehicles` |

**`searchType` values used by the scraper:**

- `company_name` — **primary** discovery via specific operator names (`Tesla Robotaxi`, `Waymo`, `Zoox`, …) plus optional secondary broad terms (`Robotics`, `Mobility`, `AI`)
- `autonomous_vehicle_authorization_number` — **broken as of 2026-09-01** (returns `total=0` for all known AV numbers including Tesla `AV8313426653583`); do not rely on it as the seed path

Company search returns many non-AV carriers. Only rows with  
`autonomousVehicleAuthorizationNumber` + `businessEntityId` are kept.

Default page size is 20; `limit`/`offset` work, but broad terms like `LLC`/`Inc` match tens of thousands of carriers and are nearly useless for AV discovery.

### Vehicle payload

```json
{
  "vehicles": [
    {
      "vin": "7SAYGDEE5TF563340",
      "make": "TESLA",
      "model": "Model Y",
      "modelYear": 2026
    }
  ]
}
```

- Fleet size = `len(vehicles)`
- `vehicle_type` = most common `model`
- `vehicle_composition` = counts grouped by `(make, model, modelYear)`, sorted by count desc

### Breaking change (2026-07-30)

Removed / broken for machine clients (HTTP 200 + SPA HTML shell):

- `GET /api/TruckStop/operators/{authorizationNumber}`
- `GET /api/TruckStop/operators/{authorizationNumber}/vehicles`

Old search shape used `autonomousVehicleRegistrations[]`; current shape uses `results[]` with  
`autonomousVehicleAuthorizationNumber` / `autonomousVehicleStatus`.

Impact: from ~2026-07-30 23:01 UTC until the company-API fix, the scraper saved **0 operators** while the UI still showed the last successful snapshot (stale numbers). That gap is why `/health` and the dashboard warning banner exist.

Field-level notes: [`../scraper/selector_findings.txt`](../scraper/selector_findings.txt).

## Scrape health

Table `scrape_health` (singleton `id = 1`) is updated every scrape run:

| Column | Meaning |
|--------|---------|
| `last_attempt_at` | Every run |
| `last_success_at` | Updated only when ≥1 operator was saved |
| `operators_ok` / `operators_failed` | Counts for that run |
| `last_error` | Truncated failure summary |
| `status` | `ok` \| `degraded` \| `failed` \| `no_data` |

API `GET /health` merges this row with the latest snapshot age:

- **stale** if last successful data is older than **45 minutes** (3 × 15‑min interval)
- Status priority for UI: `failed` > `stale` > `degraded` > `ok` > `no_data` (worst applicable wins for failures/stale)

## Frontend warnings

| Health `status` | Header label | Banner |
|-----------------|--------------|--------|
| `ok` | Live | (none) |
| `degraded` | Degraded | 일부 운영사 수집 실패 |
| `stale` | Stale | 데이터가 오래됨 |
| `failed` | Offline | 데이터 수집 실패 |
| `no_data` | No data | 데이터 없음 |

Implementation: `frontend/src/components/ScrapeWarning.jsx`, `Header.jsx`.

## Discovery strategy (2026-09-01)

1. Seed known operators via `company_name` searches using specific names, with hardcoded `(auth_number, businessEntityId, search_name)` tuples as fallback when search misses — so Tesla is always scraped when online.
2. Specific operator name terms for additional discovery.
3. Optional broad terms (`Robotics` / `Mobility` / `AI`) only as a secondary pass.

Auth-number search returning empty is why Tesla was stuck at the 2026-08-13 snapshot (186 Model Y) while the live fleet was already Model Y + Cybercab.

## Known limits

- Auth-number search currently returns empty; company_name + hardcoded `businessEntityId` is the reliable path.
- Name search alone can still miss rebranded operators; hardcoded BE ids cover known seeds.
- Operators only present in old snapshots (not re-discovered) keep old `captured_at` until they appear in search again.
- Certificate vehicle lists (`/certificate/vehicles`) are **not** AV fleets; do not use for robotaxi counts.
