# Architecture

## Overview

```
Browser (HTML/CSS/JS, Leaflet)            Flask application (backend/)               Storage
──────────────────────────────            ─────────────────────────────               ───────
Pages rendered by Jinja        ──GET──►   routes/pages.py      (HTML)
fetch("/api/v1/...")           ──JSON─►   routes/api/          (JSON, /api/v1 = /api)
                                           │  utils/responses.py (envelope, ApiError)
                                           ▼
                                          services/            (business logic)  ──►  SQLite via
                                          models/              (SQLAlchemy ORM)        SQLAlchemy
                                          errors.py · security.py · cli.py             instance/speedspot.db
Speed test ──► M-Lab ndt7 servers (see docs/decisions/0001-speed-test-engine.md), never our server
```

## Layers and responsibilities

| Layer | Folder | Rule |
|---|---|---|
| Routes | `backend/routes/` | Thin. Parse the request, call a service, return a response. No business logic |
| Services | `backend/services/` | Business rules (scoring, aggregation, seeding). Testable without HTTP |
| Models | `backend/models/` | Database tables only |
| Utils | `backend/utils/` | Small pure helpers (response envelope, and later geohash and validation) |
| Cross-cutting | `errors.py`, `security.py`, `cli.py`, `config.py`, `extensions.py` | Registered once in `create_app()` |
| Frontend | `frontend/templates`, `frontend/static` | Jinja pages, design-token CSS, plain JS modules (no build step) |

## Data model

| Model | Table | Holds |
|---|---|---|
| `Region` | `regions` | India, 36 states/UTs, 785 districts, 3,725 cities: hierarchy, codes, bounding boxes |
| `GridCell` | `grid_cells` | Neighbourhoods (geohash-6) and blocks (geohash-7) that have tests, with geometry and region codes (looked up once per cell) |
| `Measurement` | `measurements` | One test: four metrics, server-calculated NQI, block, region codes, provider and ASN, flags. **No IP, GPS or device ID** |
| `Provider`, `ProviderASN` | `providers`, `provider_asns` | 18 Indian providers and their 34 verified ASNs |
| `AreaStatistic` | `area_statistics` | **Cache** of area summaries. Invalidated when a test arrives and expires after 30 min. Always rebuildable from `measurements` |

## Measurement pipeline (`POST /api/measurements`)
1. `services/measurements.validate()` checks every field and reports all problems at once.
2. `services/grid.ensure_block()` finds or creates the block and neighbourhood cells. A block outside India gets a 422.
3. `services/providers.identify(ip)` does IP → ASN (local DB-IP file) → provider, or other ISP, VPN/cloud, or unknown. **The IP is discarded here.**
4. `services/nqi.calculate()` gives the score, always on the server.
5. VPN/cloud and implausible values are stored with `flagged=True` and a `flag_reason`, and excluded from scores.
6. `services/stats_cache.invalidate_block()` drops cached summaries for that block, neighbourhood, city, district, state and India.

## Production
- **Gunicorn** (`gunicorn.conf.py`, access log off) behind Render's proxy (`ProxyFix`, `TRUSTED_PROXY_COUNT`).
- **PostgreSQL** via psycopg 3 (the URL is normalised in `config.database_url()`). Production refuses ephemeral SQLite.
- **Alembic migrations** (`migrations/`, Flask-Migrate, `render_as_batch` so SQLite can also be migrated). `flask init-db` = upgrade + reference data.
- **WhiteNoise** serves pre-compressed static files. HTTPS redirect + HSTS.
- See [DEPLOYMENT.md](DEPLOYMENT.md).

## Filters, navigation, reports
- `services/stats.Filters` (period, provider) flows from `routes/api/areas.parse_filters()` into every row query. The cache is bypassed for filtered views.
- Guided navigation: `services/stats.nearby_destinations()` (server: candidates from block codes) + `frontend/static/js/navigate.js` (browser: exact distance, FOSSGIS walking route, Google Maps link).
- CSV: `routes/api/stats.export_areas()`, aggregates only.

## Key decisions

| Decision | Reason |
|---|---|
| **Application factory** `create_app(config_name, overrides)` | Each test gets a fresh, isolated app. Production, development and testing are configured differently |
| **Config classes + environment variables** | Secrets stay out of code. Production refuses to start without `SECRET_KEY` |
| **Versioned JSON API** (`/api/v1`) with one envelope | Predictable for the frontend, and allows changes later without breaking anything |
| **Friendly errors**: JSON for the API, an HTML page for people | No stack traces or jargon ever reach users |
| **Strict security headers** (CSP, no framing, no sniffing; HSTS in production) | Defence in depth from day one. External hosts are added to the CSP one at a time, only when a feature needs them |
| **Server-rendered pages + vanilla JS** | Fast on low-end phones, nothing to compile, easy to learn |
| **System font stack** | No font download and no third-party font requests |
| **Regions as data, cells as computed codes** | See [GEOSPATIAL.md](GEOSPATIAL.md) |
| **Python 3.12 via `uv`** | 3.9 is end-of-life. `uv` installs Python per-user without touching the system |

## Request lifecycle (example: `GET /api/v1/regions/IN-TN`)
1. Flask matches the route in `routes/api/core.py` (the `api` package splits routes by topic).
2. The view queries `Region` through SQLAlchemy, which uses parameterised SQL and so can't be injected.
3. `ok(region.to_detail())` wraps the result in `{"data": ...}`.
4. `security.py` adds the security headers.
5. An unknown code raises `ApiError("not_found", ...)`, which `errors.py` turns into a 404 JSON envelope.
