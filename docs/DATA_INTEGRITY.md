# Data Integrity: Genuine Measurements Only

SpeedSpot Mapper shows **only genuine speed tests** that real people ran and chose to share. Nothing on any page is generated, sampled or hard-coded.

## How this is enforced

| Layer | Guarantee |
|---|---|
| **Code** | There is no demo-data generator. The former `backend/services/demo_data.py`, the `flask demo-data` commands and the `ALLOW_DEMO_DATA` / `SPEEDSPOT_ALLOW_DEMO_DATA` switch were removed (2026-11-01) |
| **Database** | `measurements.source` has a CHECK constraint `source = 'user'`, so the database itself refuses any other kind of row |
| **Migration** | `b7c1e2d3f4a5_genuine_data_only` deletes any previously generated rows, the grid cells that only existed for them, and the statistics cache |
| **Queries** | Every statistic (map, rankings, distribution, trends, weak areas, counts, latest test, CSV, navigation) is computed from `source = 'user'` rows that aren't flagged (VPN/implausible) and are inside the chosen time window |
| **UI** | No demo banners or labels. Empty data shows honest empty states (see below) |

## Empty states (no fabricated fallbacks)

| Place | Message when there's no data |
|---|---|
| Home | "Help map India's connectivity. Run your first speed test and contribute an anonymised measurement." |
| Map panel | "No measurements yet in this area." (badge: *No tests yet*) |
| Insights | "Connectivity insights will appear as genuine community measurements arrive." |
| Compare Providers | "Not enough measurements to compare providers in this area yet." |
| Guided navigation | "We don't have enough recent measurements nearby to recommend a better-connected area." |

Three states always stay separate: **No tests yet** (zero tests), **Not enough tests** (some, below the minimum), and **Weak** (enough tests, low score).

## Synthetic data in automated tests only
Tests need known data, so `tests/conftest.py::add_tests` and `tests/e2e/conftest.py` insert rows into **temporary databases** (in-memory SQLite, a throwaway file, or a throwaway PostgreSQL) that are destroyed after the test run. The application never imports test code, and the normal and production databases never receive these rows. `tests/integration/test_data_integrity.py` checks all of the above.
