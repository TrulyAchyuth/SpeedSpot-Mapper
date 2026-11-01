# SpeedSpot Mapper — Project Status

_Last updated: 2026-11-01 (pushed to GitHub)_

## Current status

**Ready for the campus pilot, pending deployment.** Every planned pilot feature is built and tested. Render deployment is **prepared and rehearsed locally**. The code is on GitHub. Going live needs the project owner's Render account and a paid database plan (see `docs/DEPLOYMENT.md`).

## Phase overview

| Phase | Name | Status |
|---|---|---|
| 0–5 | Foundations, core logic, measurement API + provider detection, speed test, India map, provider comparison | ✅ Done |
| 6 | Guided navigation | ✅ Done |
| 7 | City insights (distribution, weak zones, providers, density, trends, district comparison, CSV) | ✅ Done |
| 8 | Accessibility, responsive QA | ✅ Automated axe + layout tests pass. A manual screen-reader pass is still recommended |
| 9 | Security hardening and deployment preparation | ✅ Prepared and rehearsed. ⏳ **Not deployed** (needs owner account) |
| 10 | Campus pilot | ⏳ Next |

## GitHub repository (2026-11-01)
- **Repository:** https://github.com/TrulyAchyuth/speedspot-mapper
- **Owner:** `TrulyAchyuth` (sole collaborator, admin). No other collaborators, invitations or deploy keys.
- **Visibility:** private. **Default branch:** `main`.
- **Initial commit:** `9c1d852595d3325013363c50e331e75b0a3744a4` ("Initial commit: SpeedSpot Mapper India-wide connectivity platform"), 184 files. Pushed and verified: the remote `main` matches this commit.
- Left out of git: `.env`, local databases, the ASN database, `.venv/`, screenshots, the scratch backup, and the original presentation file (it contains personal details).

## Final release audit (2026-11-01)
- **Migration safety:** `b7c1e2d3f4a5_genuine_data_only` was tested on an existing SQLite database and on **PostgreSQL 16**. Both start from the old schema with genuine rows, generated rows (including one inside a genuine block), their cells and a cached statistic.
  - Genuine rows and their cells are kept. Generated rows, generated-only cells and the cache are removed. The demo columns are dropped and `source = 'user'` is enforced.
  - Downgrade restores the old schema without losing genuine rows, and re-upgrading works. A fresh database migrates from scratch (`flask init-db` test).
  - Tests: `test_data_integrity.py::test_migration_on_existing_sqlite_database`, `test_postgres.py::test_genuine_data_migration_on_postgresql`.
- **Cancellation:** after a cancel, the engine ignores late callbacks. `test_speed_test_cancellation_is_complete` verifies:
  - the cancelled message appears
  - a real ndt7 worker is terminated
  - the native `Worker` is restored
  - a late engine result shows nothing and submits nothing, even with sharing on
  - a following test completes and is stored exactly once

  Limit: ndt7-js's initial server-lookup request can't be aborted (no API). It finishes and is ignored.
- **Real speed test (M-Lab, Chennai server):** 153.08 Mbps down, 18.66 Mbps up, 39.3 ms latency, 0.5 ms stability (TCP RTTVar), score 94. About 20 s. Not submitted: sharing was off because the automated browser has no genuine location. The submission path is covered by integration and browser tests.
- **Tests:** `pytest` **335 passed, 0 skipped, 0 failed** (71 unit, 175 integration, 89 browser). JS **4 passed**.
- **Git audit:** no secrets, tokens or keys in the 184 committed files. `.env`, `instance/` (local database), `data/` (ASN database), `.venv/`, caches, screenshots and test output are ignored. The scratch backup of the removed generated rows lives outside the repository.

## Genuine data only (2026-11-01)
- **Removed the demo-data tool entirely:** `backend/services/demo_data.py`, the `flask demo-data` commands, the `ALLOW_DEMO_DATA` / `SPEEDSPOT_ALLOW_DEMO_DATA` switch (including the local `.env` line), the demo cache scope, every `includes_demo`/`is_demo` field, the CSV demo column, the demo banner and its CSS, the "includes demo data" notes and the banner icon.
- **Database:**
  - Migration `b7c1e2d3f4a5_genuine_data_only` deleted the 2,727 generated measurements, the 3,540 grid cells that only existed for them, and the 75 cached statistics from the dev database (backup kept in the session scratchpad).
  - `CHECK (source = 'user')` now makes the database refuse anything else.
  - The migration is reversible (schema only) and drift-checked.
- **Empty states**, exactly as requested, on Home, the map panel, Insights, Compare Providers and guided navigation. "No tests yet", "Not enough tests" and "Weak" stay separate.
- **Speed test:** when M-Lab's server finder is rate-limiting (HTTP 429), the message now says so instead of blaming the user's network.
- **Tests:** the demo tests were replaced by stronger guarantees in `tests/integration/test_data_integrity.py`:
  - The generator is gone and the database rejects non-genuine rows.
  - No API response or page mentions demo data.
  - An empty database gives honest empty answers.
  - The migration cleans old demo rows.
  - Fixtures (`tests/conftest.py`, `tests/e2e/conftest.py`) write only to temporary databases.
- **Chrome warning:** `--disable-blink-features=AutomationControlled` is added by the **Playwright MCP server** (`@playwright/mcp` 0.0.84, its config resolver in `playwright-core/lib/coreBundle.js`), which Claude Code's Playwright plugin starts with `npx @playwright/mcp@latest`. It isn't in this repository. The project's own browser tests (pytest-playwright) were verified to launch Chromium **without** the flag. See the final report for the options.
- **Results:** `pytest` **334 passed**, JS 4 passed, bandit clean, pip-audit clean.
- **Not re-verified:** a fresh end-to-end real speed test was blocked by M-Lab rate-limiting this network (429). The last successful real test was earlier on 2026-11-01.

## Product redesign (2026-11-01)
- **App shell:** a collapsible left sidebar on desktop (full width from 1200 px, icon rail with tooltips below that, choice remembered), and a phone top bar with a "More" menu sheet plus the bottom tab bar. One consistent demo-data banner.
- **Homepage:** rebuilt on real API data:
  - Hero with an India illustration generated from LGD boundaries.
  - Overview cards and data-availability bar.
  - Interactive state map with search.
  - Four quick actions.
  - Neighbourhood distribution, and facts shown only when the data supports them.
  - How it works and the privacy promise.
- **Insights:** context → 4 equal overview cards → distribution → quality over time (with Good/Fair reference lines) → density → providers → weak areas → sub-area comparison → CSV. Filters sit in one toolbar.
- **Speed test:** a **Cancel** button (terminates the ndt7 workers) and a "Technical details" section.
- **Compare Providers:** a plain-language verdict.
- **Map:** an "All of India" button, the `?nearby=1` shortcut, and resizing when the sidebar changes.
- **New pages:** About SpeedSpot, How it works.
- **Fixed during the redesign:**
  - A **cache race** returned 500 when the homepage loaded two endpoints at once (now handled, with a test).
  - The illustration generator dropped nested geometries.
  - A speed-test syntax error.
  - The sidebar animated on first paint.
- **Tests:** **324 passed** (89 browser tests). They cover the sidebar collapse, tooltips and persistence, the tablet rail, the phone menu, speed-test cancel, the home overview and mini-map, the Insights section order, no sideways scrolling on 8 pages at 6 widths (360–1440 px), and axe accessibility on 10 views. JS: 4 passed.

## Added in the previous milestone
- **Filters:** time period (7/30/90/180 days) and provider (or "not identified") on the map, insights, statistics, lists, navigation and CSV. Rankings take the period filter only. Filtered views bypass the cache.
- **Measurement density:** "Colour the map by: Number of tests" mode, and a density breakdown in Insights. The legend now separates **"No tests yet"** from **"Not enough tests"**.
- **Provider rankings:** the minimum is now **5 tests per provider per area**, as the specification requires. Sample counts and latest test are shown. Unidentified providers are counted but not ranked.
- **Guided navigation:** "Find a better connection nearby".
  - Suggests Good areas that have ≥ 5 tests and beat the current area by ≥ 5 points, within 1.5 km (widenable to 3 km). Ranked by score minus distance.
  - The server receives only the ~150 m area code.
  - Shows markers, straight-line distance and an estimated walk time.
  - **Walking route** on request via FOSSGIS (OSRM foot profile), with disclosure, attribution and a "Fix the map" link. There's a "Open in Google Maps" fallback, and a dashed direction line if routing fails.
  - The "not a guarantee" notice is always shown.
- **Insights:**
  - Trend: weekly or 30-day medians, shown only when 3 or more periods have ≥ 5 tests.
  - Density.
  - "Weak connectivity zones", which now exclude Good areas.
  - **CSV reports** by sub-area or by neighbourhood (aggregates only).
- **Integrity:**
  - Duplicate-submission protection: a random per-test UUID with a unique constraint returns 409.
  - CHECK constraints on every metric and enum.
  - Foreign keys enforced on SQLite.
  - 64 KB request limit (413).
- **Migrations:** Alembic via Flask-Migrate, initial migration verified with no drift on SQLite and PostgreSQL. `flask init-db` = migrate + seed.
- **Production:**
  - PostgreSQL (psycopg 3) with URL normalisation.
  - Production **refuses ephemeral SQLite**.
  - WhiteNoise compressed static files.
  - HTTPS redirect + HSTS.
  - Gunicorn config with **access logs off**.
  - `render.yaml` (Singapore region, Postgres `basic-256mb`, plan names checked against Render's schema) and `.python-version`.
- **Providers:** Sify (AS9583) added after the real-world test showed this network is Sify. Now 18 providers and 34 verified ASNs.
- **Docs:** new `docs/DEPLOYMENT.md`, `docs/TESTING.md`, `docs/PRIVACY.md`. README, API and architecture docs updated.

## Integration verified (end to end)

| # | Feature | How it was verified |
|---|---|---|
| 1–3 | India map, state/district navigation, neighbourhood exploration | Browser tests (drill-down, search, filters, density) + screenshots |
| 4 | **Genuine speed test** | **A real M-Lab ndt7 test ran in Chromium**: 150 Mbps down, 14.6 up, 49 ms, 35 ms stability, against a Chennai server |
| 5 | Consent-based geolocation | Browser tests: permission sheet, "Not now", share flow; the POST contains a 7-character cell, never lat/lng |
| 6 | Provider identification | Real DB-IP lookups in tests (Jio, Cloudflare→VPN); production rehearsal behind a proxy → Jio |
| 7–9 | NQI, submission, grid aggregation | Unit + integration tests; production rehearsal POST scored 74 |
| 10–11 | Connectivity map, provider rankings | Integration + browser tests |
| 12 | Guided navigation | Browser test with a stand-in route: list, markers, route distance and time, attribution, privacy of the request |
| 13 | City insights | Integration tests + browser test (CSV download) |
| 14 | Mobile responsiveness | No sideways scrolling on all 6 pages at 360, 390, 768 and 1280 px (24 browser tests) |

## Test results (actual output)
- `pytest` (after the redesign): **324 passed**. Before the redesign: 287 passed in about 60 s, run twice with identical results.
  - Unit: 71 · Integration: 163 (including 3 on real PostgreSQL 16) · Browser e2e: 53.
- `node --test "tests/js/*.test.mjs"`: **4 passed**.
- `pip-audit -r requirements.txt` and `-r requirements-dev.txt`: **no known vulnerabilities**.
- `npm audit` (vendored Leaflet 1.9.4, ndt7 0.1.5): **0 vulnerabilities**.
- `bandit -q -r backend scripts`: **exit 0** (3 reviewed false positives marked).
- **Accessibility:** axe-core reports **no serious or critical violations** on 8 views at 390 and 1280 px.
- **Production rehearsal** (Gunicorn + PostgreSQL + WhiteNoise + proxy headers):
  - Health 200 and HTTP → 301 HTTPS.
  - HSTS present, no demo banner.
  - GeoJSON gzip-compressed 553 → 155 KB.
  - Provider identified via X-Forwarded-For.
  - POST 201.
  - Gunicorn log contained **no visitor IP**.

**Bugs found and fixed by this milestone's tests:**
- A PostgreSQL-only `GROUP BY` error in the measurement list.
- Two mobile layout overflows on Insights (grid tracks).
- Two test problems: an engine stand-in being overwritten, and CSP-blocked waits.

## Real-world speed-test validation
Same machine and network, one sample each:

| | SpeedSpot (M-Lab) | Reference |
|---|---|---|
| Download | 150 Mbps | 105–161 Mbps |
| Upload | 14.6 Mbps | 30–31 Mbps |
| Latency | 49 ms | 37–42 ms |

Download and latency are consistent. **Upload was about half the reference.** This needs repeated comparison during the pilot before it's trusted (see `docs/TESTING.md`). This test published the machine's public IP to M-Lab's open data, as disclosed.

## Known limitations
- **Not deployed.** Needs a Render account and payment for durable Postgres (the GitHub repository exists). Production behaviour on Render itself (proxy hop count, cold starts) is unverified.
- Upload accuracy is unconfirmed (above). Jitter is approximate (TCP RTT variation under load).
- OpenStreetMap tiles and FOSSGIS routing are free, light-use services. Wider public use needs a tile provider and possibly a routing provider.
- LGD boundaries haven't been formally checked against the Survey of India map. Cities are point-based.
- VPN detection is best-effort. DB-IP Lite is less complete than paid data and needs monthly refresh.
- Rate-limit counters are in memory per process.
- No manual screen-reader (VoiceOver/TalkBack) or real-device testing yet.
- See `docs/PRIVACY.md` for remaining privacy limitations (M-Lab IP publication, determined manipulation, sparse blocks).

## Remaining work
1. **Owner:** create the Render Blueprint from the GitHub repository, then verify per `docs/DEPLOYMENT.md`.
2. Pilot: repeated real-world tests (especially upload), a manual screen-reader pass, and testing on low-end Android phones.
3. Before wider launch: a tile provider, a shared rate-limit store (Redis) if scaled out, and a formal boundary review.
