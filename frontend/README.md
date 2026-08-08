# Frontend (React + Vite)

Texas Robotaxi Tracker dashboard UI. Production build is served by Nginx with TLS (see `Dockerfile`, `nginx.conf`).

## Local dev

```bash
npm install
npm run dev
```

Point API base at the backend (`/api` proxy is configured for production Nginx; for Vite dev you may need a proxy in `vite.config.js` or run against `http://localhost:8000`).

## Production (Docker)

Built and served as the `frontend` service:

- Host: **https://localhost:8443**
- Proxies `/api/*` → `api:8000`
- TLS certs from `../certs/` (paths in `nginx.conf`)

## Key UI pieces

| Component | Role |
|-----------|------|
| `Header.jsx` | Live / Degraded / Stale / Offline + push button |
| `ScrapeWarning.jsx` | Banner when `/health` status ≠ `ok` |
| `SummaryCards.jsx` | Tesla card + composition |
| `TrendChart.jsx` / `ComparisonChart.jsx` | Charts |
| `ChangeLog.jsx` | Count-change events |

See root [README.md](../README.md) and [docs/DATA_SOURCE.md](../docs/DATA_SOURCE.md).
