# Deploying SpeedSpot Mapper on Render

**Status: production deployment is still pending.** The code is on GitHub at https://github.com/TrulyAchyuth/speedspot-mapper (private, owner `TrulyAchyuth`, branch `main`). Deploying needs a Render account and a payment method, which are manual steps for the project owner. Nothing has been deployed or verified in production.

## What's prepared

| File | Purpose |
|---|---|
| `render.yaml` | Render Blueprint: web service + PostgreSQL database in Singapore (closest region to India). Field values checked against Render's published schema |
| `gunicorn.conf.py` | Production server. **Access logging off** (it would record visitor IPs). One worker × 4 threads by default |
| `wsgi.py` | `create_app("production")` |
| `.python-version` | Python 3.12 |
| `migrations/` | Alembic migrations (`flask init-db` applies them, then loads reference data) |
| `requirements.txt` | Pinned runtime dependencies, including `psycopg[binary]` and `whitenoise` |

## Why the database is PostgreSQL, not SQLite
Render's filesystem is **ephemeral**: a SQLite file is wiped on every redeploy, restart, or free-tier spin-down. Persistent disks are paid-only and can't be attached to free web services. Render's **free** Postgres is deleted 30 days after creation and has no backups. So:

- **Recommended (as in `render.yaml`):** Render Postgres `basic-256mb` (paid) with the web service on the free plan.
- **Lower-cost alternative:** a free external PostgreSQL that doesn't expire (for example Neon or Supabase). Remove the `databases:` block and set `DATABASE_URL` yourself.
- **The app enforces this.** In production it **refuses to start** with a SQLite URL unless `ALLOW_SQLITE_IN_PRODUCTION=true` (only sensible with a paid persistent disk).

Check current prices at https://render.com/pricing before choosing. Prices weren't confirmed from Render's own pages during preparation.

## Manual steps (project owner)
1. **Done:** the repository is on GitHub (https://github.com/TrulyAchyuth/speedspot-mapper). Because it's private, give Render access to it when connecting your GitHub account.
2. In Render: **New → Blueprint**, pick the repository, and review the plan and costs it shows, then apply.
3. Wait for the build. It installs dependencies, downloads the DB-IP ASN database, and pre-compresses static files. The start command runs `flask init-db` (migrations + reference data) and then Gunicorn.
4. **Verify after deploy:**
   - `https://<your-app>.onrender.com/api/health` returns `{"data": {"status": "ok", "database": "ok"}}`.
   - The site loads over **HTTPS**. Plain HTTP redirects (301). The `Strict-Transport-Security` header is present.
   - **Provider detection:** open `/api/me/provider` on mobile data. It should name your provider. If it shows a cloud/VPN network or "unknown", the proxy count is wrong: adjust `TRUSTED_PROXY_COUNT` (default `1`).
   - The Speed Test page shows your provider and completes a test. Sharing a result adds it to the map.
   - A fresh deployment shows empty states (no sample data exists anywhere in the app).

## Environment variables

| Variable | Set by | Notes |
|---|---|---|
| `SPEEDSPOT_ENV=production` | `render.yaml` | Selects the production config |
| `SECRET_KEY` | Render (`generateValue`) | Never commit. Production refuses to start without it |
| `DATABASE_URL` | Render (from the database) | `postgres://` and `postgresql://` are both accepted (converted for psycopg 3) |
| `TRUSTED_PROXY_COUNT=1` | `render.yaml` | Reverse proxies in front of the app. Verify as above |
| `WEB_CONCURRENCY=1` | `render.yaml` | Gunicorn workers. Each loads the district boundaries (about 100 MB) |
| `FORCE_HTTPS` | default `true` | Redirect HTTP → HTTPS (`/api/health` is exempt for health checks) |
| `RATELIMIT_STORAGE_URI` | default `memory://` | Use `redis://…` if you run more than one instance |

## HTTPS, CORS, static files
- **HTTPS:** Render terminates TLS. The app also redirects HTTP and sends HSTS.
- **CORS:** not enabled. The API is same-origin only, which is intentional (tested).
- **Static files:** served by WhiteNoise with pre-compressed `.gz` files. District GeoJSON drops from about 9 MB to about 2 MB on the wire. Files are cached for 1 hour.

## Ongoing operations
- **Monthly:** redeploy (or re-run `python scripts/download_asn_db.py`) to refresh the DB-IP ASN database.
- **Backups:** paid Render Postgres plans include backups. Free ones don't.
- **Map tiles:** the street map uses OpenStreetMap's servers, which allow light use only. Before wider public use, switch to a tile provider (see `frontend/static/js/pages/map.js`, `tiles`) and update the CSP in `backend/security.py`.
- **Free web plan:** spins down after 15 minutes idle, with about a minute of cold start. Use `plan: starter` to keep it awake.
