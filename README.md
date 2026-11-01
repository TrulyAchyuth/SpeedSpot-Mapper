# SpeedSpot Mapper

**Your city. Your connection.**

A friendly Smart Cities web app that helps people across India discover internet quality around them, compare providers and find better-connected neighbourhoods. You can explore from the whole country down to a ~150 m street block.

> **Status:** feature-complete for the pilot and tested (see [PROJECT_STATUS.md](PROJECT_STATUS.md)). Deployment to Render is **prepared but not performed**: it needs your Render account ([docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)).

## Requirements
- Python **3.12+**
- [uv](https://docs.astral.sh/uv/) (recommended) or `pip`
- Node.js (optional, only to run the small JS test suite)

## Setup

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -r requirements-dev.txt      # or: pip install -r requirements-dev.txt

cp .env.example .env
python scripts/download_asn_db.py           # IP→provider database (DB-IP, CC BY 4.0), ~10 MB; re-run monthly
flask init-db                               # migrations + India's states, 785 districts, 3,725 cities, providers
flask run --debug
```

Open <http://127.0.0.1:5000>. A fresh database has no measurements, so pages show friendly empty states until real speed tests are shared. SpeedSpot never generates or displays sample data ([docs/DATA_INTEGRITY.md](docs/DATA_INTEGRITY.md)).

## Tests

```bash
playwright install chromium                 # once, for browser tests
pytest                                      # unit, integration, PostgreSQL and browser tests
node --test "tests/js/*.test.mjs"           # JS: geohash, score formula, gauge scale
```
Details, including real-world validation: [docs/TESTING.md](docs/TESTING.md).

## Deployment
Render Blueprint (`render.yaml`) with PostgreSQL, Gunicorn, migrations and WhiteNoise. Read [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) first. It covers costs, why SQLite isn't used in production, and the manual steps.

## Rebuilding the boundary files (rarely needed)

The simplified GeoJSON in `frontend/static/geo/` and the reference JSON in `backend/reference/` are committed. To rebuild them from the original sources, download these into `data/raw/` (git-ignored):

- `LGD_States.geojson` and `LGD_Districts.geojson` from [bharatlas.com](https://bharatlas.com) (layers `lgd_states`, `lgd_districts`)
- `cities15000.zip` from <https://download.geonames.org/export/dump/>

Then run `python scripts/build_boundaries.py`.

## Project layout

```
backend/
  routes/api/       JSON API (/api/v1): core, stats, measurements
  routes/pages.py   HTML pages
  services/         nqi, measurements, providers (IP→ASN), grid, stats, stats_cache, geo_lookup, regions
  models/           Region, GridCell, Measurement, Provider/ProviderASN, AreaStatistic
  reference/        committed reference data (states, districts index, cities, providers)
frontend/
  templates/        Jinja pages + partials (sprite, icons, location dialog)
  static/css/       tokens · base · components · map
  static/js/        shared modules + pages/ (home, map, speedtest, providers, insights)
  static/geo/       simplified LGD boundaries (states + per-state districts)
  static/vendor/    Leaflet 1.9.4, M-Lab ndt7 0.1.5 (pinned copies)
scripts/            build_boundaries.py, download_asn_db.py
migrations/         Alembic database migrations
render.yaml, gunicorn.conf.py, wsgi.py   production deployment
tests/              unit/, integration/ (incl. PostgreSQL), e2e/ (browser + accessibility), js/
docs/               architecture, API, geospatial, privacy, testing, deployment, design system, data integrity
```

## Data, libraries and licences
- **Boundaries:** Local Government Directory (LGD), Government of India, via bharatlas.com (CC0-1.0 / CC-BY-4.0).
- **Cities:** GeoNames (CC-BY 4.0).
- **Street tiles:** © OpenStreetMap contributors (ODbL), used under the OSM Tile Usage Policy (light use only).
- **Speed test:** M-Lab ndt7-js (Apache-2.0). M-Lab publishes test results, including IP addresses, as open data, and users are told this before testing. Why M-Lab: [docs/decisions/0001-speed-test-engine.md](docs/decisions/0001-speed-test-engine.md).
- **Provider detection:** IP to ASN Lite by [DB-IP.com](https://db-ip.com) (CC BY 4.0), read locally, so no third party sees visitors' IPs.
- **Walking routes:** FOSSGIS OSRM foot routing (routing.openstreetmap.de), requested from the browser only when the user asks. Attribution and a "Fix the map" link are shown.
- **Map library:** Leaflet (BSD-2-Clause). **Font:** Inter (SIL OFL 1.1).

## Privacy in one paragraph
Your exact location never leaves your device: it's turned into a ~150 m area code first. SpeedSpot never stores your IP address. It's used in memory to recognise your provider, and rate-limit counters live briefly in memory only. There are no accounts and no tracking cookies. Test times are rounded to the hour, and areas need enough tests before a score appears.

## Documentation
[PROJECT_PLAN.md](PROJECT_PLAN.md) · [PROJECT_STATUS.md](PROJECT_STATUS.md) · [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/API.md](docs/API.md) · [docs/GEOSPATIAL.md](docs/GEOSPATIAL.md) · [docs/PRIVACY.md](docs/PRIVACY.md) · [docs/TESTING.md](docs/TESTING.md) · [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) · [docs/DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md) · [docs/DATA_INTEGRITY.md](docs/DATA_INTEGRITY.md) · [docs/decisions/](docs/decisions/)

## Team
SpeedSpot Innovators: Achyuth and Jeevan. BCSE316L Design of Smart Cities, DA2 mini project.
