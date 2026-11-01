# Privacy and Security

This is the technical counterpart of the public Privacy page (`/privacy`).

## Data flows

| Data | Where it goes | Stored by SpeedSpot? |
|---|---|---|
| Exact GPS position | Stays in the browser. It's turned into a geohash-7 (~150 m) code on the device | **Never** |
| ~150 m area code | Sent only if the user switches on "Add my result to the community map", plus for "locate me" and guided navigation | Only with a shared test (plus the block's centre point, which is no more precise than the block) |
| IP address | Seen by our server on every request | **Never stored or logged by the app.** Used in memory for IP → ASN lookup and rate limiting. Gunicorn access logs are off |
| Provider / ASN | Derived from the IP | Yes (identifies a company, not a person) |
| Test results | Browser → our server | Yes, with the time rounded to the hour |
| Submission ID | A random UUID made by the browser for each test | Yes, only to reject duplicate uploads. A new one is made every time, so it can't link tests together |
| IP address (to M-Lab) | The browser connects to M-Lab for the test | **M-Lab publishes it** with the result, permanently. Disclosed before every test |
| Start and end points (to FOSSGIS) | Only when the user taps "Show walking route" | Not by us. FOSSGIS keeps them in its logs (disclosed in the UI) |

## Protections and where they live

| Protection | Implementation | Tested in |
|---|---|---|
| No raw coordinates accepted | API accepts only `cell_id` (geohash-7), never lat/lng | `test_measurements.py`, `test_intelligence.py`, e2e |
| No IP stored | No IP columns. Every table scanned for the IP in tests | `test_measurements.py::test_nothing_identifying_is_stored` |
| Small-number protection | Area scores need ≥ 5 tests. Public lists hide the neighbourhood until it has ≥ 5 tests. Lists and CSV never show the ~150 m block | `test_stats.py`, `test_measurements.py`, `test_intelligence.py` |
| Input validation | Every field checked, all errors reported at once. 64 KB body limit | `test_measurements.py`, `test_security.py` |
| Database integrity | CHECK constraints on every metric and enum, foreign keys enforced (SQLite PRAGMA, always in PostgreSQL), unique submission IDs | `test_integrity.py`, `test_postgres.py` |
| SQL injection | All queries via the SQLAlchemy ORM with bound parameters. Search strips `%`/`_` wildcards | `test_api.py` |
| XSS | Jinja auto-escaping, `textContent` in JS, strict CSP (`script-src 'self'`, no `unsafe-inline`/`unsafe-eval`) | `test_security.py`, e2e |
| Rate limiting | 30 submissions/hour per network, one bucket shared across `/api` and `/api/v1` | `test_measurements.py` |
| Duplicate submissions | Random `submission_id` per test with a unique constraint, giving 409 on repeats | `test_integrity.py`, `test_postgres.py` |
| Abuse in scores | Medians, ≥ 5-test rules, implausible values and VPN/cloud results kept out of scores | `test_stats.py`, `test_measurements.py` |
| CORS | Not enabled: same-origin only | `test_security.py::test_no_cors_headers_are_sent` |
| HTTPS | Redirect + HSTS in production | `test_security.py` |
| Secrets | `.env` git-ignored. `SECRET_KEY` required in production. Render generates it | `test_config.py` |
| Dependencies | `pip-audit` (Python) and `npm audit` (vendored Leaflet, ndt7): 0 known vulnerabilities on 2026-11-01 | manual |
| Static analysis | `bandit`: 0 open findings (3 reviewed false positives marked `nosec`) | manual |

## Remaining limitations (honest list)
- **M-Lab publishes test IPs** permanently. This is unavoidable with M-Lab and disclosed to users.
- **Determined manipulation:** results are measured in the browser, so someone could submit invented numbers from many networks. Rate limits, medians, minimum counts and plausibility checks reduce the impact but can't prevent it. A future option is server-side verification of M-Lab results, though linking M-Lab test IDs would re-expose IPs, so this needs care.
- **Rate-limit counters** live in each process's memory: they reset on restart and aren't shared between instances.
- **The Werkzeug development server** prints client IPs to the terminal. Production (Gunicorn) has access logs off. The hosting provider's own edge logs are outside our control.
- **VPN detection** is best-effort (known cloud/VPN networks and name patterns).
- **Sparse areas:** a shared test stores the block and the hour. In a very quiet block, someone who knows a person tested there could guess which test it was. Public views hide blocks and small groups, but the database itself holds them.
