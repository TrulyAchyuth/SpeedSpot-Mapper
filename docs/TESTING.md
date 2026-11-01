# Testing SpeedSpot Mapper

## Run everything

```bash
source .venv/bin/activate
uv pip install -r requirements-dev.txt
playwright install chromium            # once, for the browser tests
pytest                                 # Python unit, integration, PostgreSQL and browser tests
node --test "tests/js/*.test.mjs"      # JavaScript unit tests
pip-audit -r requirements.txt          # known vulnerabilities in dependencies
bandit -q -r backend scripts           # static security analysis
```

## What each layer covers

| Folder | What it checks |
|---|---|
| `tests/unit/` | NQI formula and band boundaries (70/69, 40/39), geohash reference vectors, aggregation honesty rules, cache behaviour, provider identification (including against the real DB-IP file when present), config safety, reference data |
| `tests/integration/` | Every API endpoint through Flask's test client: validation (all fields, NaN, oversize bodies), server-side scoring, persistence, duplicate submissions, database CHECK and foreign-key constraints, privacy (no IP or coordinates stored in **any** table), filters, guided navigation, trends, density, CSV export, rate limiting, HTTPS redirect, no CORS, Alembic migrations (applied fresh, no drift) |
| `tests/integration/test_postgres.py` | The same migrations and key queries on a **real PostgreSQL 16** server started by `pgserver`. This caught a `GROUP BY` bug SQLite allowed. Skipped if `pgserver` isn't installed |
| `tests/e2e/` | Chromium via Playwright against the real app: every page without console errors, map drill-down, keyboard search, filters and density mode, guided navigation with routing, the speed-test flow with and without sharing, CSV download, **no sideways scrolling** at 360/390/768/1280 px, and **axe-core accessibility** (no serious or critical violations) on 8 views × 2 widths |
| `tests/js/` | Geohash parity with Python, the score formula, the gauge scale |

## Stand-ins used in tests (and only in tests)
- **Speed-test engine:** browser tests replace `/static/vendor/ndt7/ndt7.js` with a clearly labelled stand-in, so the page flow runs offline. The app itself never simulates a measurement.
- **Walking routes:** the FOSSGIS response is replaced with a fixed route in OSRM's format.
- **IP → ASN:** `FakeAsnDatabase` maps a few public IPs. Separate tests use the real DB-IP file when it's downloaded.
- **Network:** browser tests block every host except the app (map tiles get a blank image).

## Real-world speed-test validation (manual)
Run a real test on the Speed Test page and compare it with an independent reference on the same network, at the same time. **Note:** a real M-Lab test publishes your public IP address in M-Lab's open data.

Recorded on 2026-11-01 (one sample each, same machine and network):

| | SpeedSpot (M-Lab ndt7, Chennai server) | Reference |
|---|---|---|
| Download | 150 Mbps | 105–161 Mbps (Cloudflare, 3 × 50 MB via curl) |
| Upload | 14.6 Mbps | 30–31 Mbps (Cloudflare, 2 × 10 MB via curl) |
| Latency | 49 ms (TCP MinRTT) | 37–42 ms (TCP connect to Cloudflare edge) |
| Stability (jitter) | 35 ms (TCP RTT variation under load) | not measured |

Download and latency agree well. **Upload measured about half the reference.** Different servers and routes may explain it, but it needs repeated comparisons during the pilot (ideally against M-Lab's own speed test at speed.measurementlab.net, which uses the same servers).
