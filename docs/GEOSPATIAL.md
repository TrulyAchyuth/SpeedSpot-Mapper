# Geospatial Data Architecture

SpeedSpot covers **all of India**: 28 states and 8 union territories. People can zoom from the whole country down to a single street block:

```
India  →  State / UT  →  District  →  City  →  Neighbourhood  →  Block (~150 m)
└───────────── administrative regions ─────────────┘  └──── geohash grid cells ────┘
```

VIT Chennai is only the first development and pilot location (`DEV_LOCATION` in `backend/config.py`).

## 1. Two kinds of "place"

| Kind | Levels | Why |
|---|---|---|
| **Administrative regions** (rows in the `regions` table, boundaries in GeoJSON) | Country, State/UT, District, City | These are the names people and governments use. Planners need results for the units they manage. |
| **Grid cells** (geohash strings, not database rows) | Neighbourhood (geohash-6), Block (geohash-7) | India has no consistent official dataset of neighbourhood boundaries. A grid is uniform, needs no boundary files, and can be computed on the user's phone, so their exact location never has to leave it. |

> **In plain words: geohash.** A geohash turns a latitude/longitude into a short code such as `tf34e2k`. Every extra character splits the area into 32 smaller squares, so a longer code means a smaller cell. Points inside the same cell share the same code, which makes grouping them easy.

### Cell sizes at Indian latitudes

A geohash cell's height is constant, but its width shrinks towards the north because lines of longitude converge.

| Level | Precision | Height | Width at 8° N (Kanyakumari) | 13° N (Chennai) | 28.6° N (Delhi) | 34° N (Srinagar) |
|---|---|---|---|---|---|---|
| Block | 7 | ~153 m | ~151 m | ~149 m | ~134 m | ~127 m |
| Neighbourhood | 6 | ~610 m | ~1.21 km | ~1.19 km | ~1.07 km | ~1.01 km |

Geohash-7 matches the spec's "~150 m" well across India.

## 2. Identifiers

| Level | Code | Example | Source |
|---|---|---|---|
| Country | ISO 3166-1 | `IN` | — |
| State/UT | ISO 3166-2:IN | `IN-TN` | Seeded now from `backend/reference/india_states_uts.json` |
| District | `<state>-D<LGD code>` | `IN-TN-D603` *(illustrative)* | Government Local Government Directory (LGD) codes, imported with district boundaries |
| City | `<state>-C<code>` | — | Decided at city import (LGD urban local body or Census town code) |
| Neighbourhood | geohash-6 | `tf34e2` | Computed |
| Block | geohash-7 | `tf34e2k` | Computed |

The `regions` table stores `lgd_code` separately, so official datasets can be joined later.

## 3. Boundary data (implemented)

| Layer | Source | Licence | Notes |
|---|---|---|---|
| States/UTs (36) | **LGD** (Local Government Directory, Government of India) boundaries, republished by [bharatlas](https://bharatlas.com) (`lgd_states`) | CC0-1.0 / CC-BY-4.0 | Matched to our ISO codes by LGD state code. Depicts all of Jammu & Kashmir and Ladakh as India's territory, consistent with the official map |
| Districts (785) | LGD via bharatlas (`lgd_districts`) | CC0-1.0 / CC-BY-4.0 | Codes `IN-XX-D<LGD>`. Muzaffarabad and Mirpur have no LGD code and use their Census 2011 code (`IN-JK-X991/X992`) |
| Cities (3,725) | [GeoNames](https://www.geonames.org) `cities15000` (populated places ≥ 15,000 people) | CC-BY 4.0 | Points only; assigned to districts by point-in-polygon |

`scripts/build_boundaries.py` turns the raw downloads (in git-ignored `data/raw/`) into committed files:
- `frontend/static/geo/states.geojson` (553 KB, simplified ~550 m) for the national view.
- `frontend/static/geo/districts/<STATE>.geojson` (8.7 MB total, simplified ~90 m, largest 906 KB), loaded only when a state is opened.
- `backend/reference/india_boundaries_index.json` (state bboxes + district list) and `india_cities.json`, which `flask init-db` loads into the `regions` table.

Districts are simplified independently, so neighbouring outlines can differ by tens of metres. That's invisible at district zoom.

**Still to verify before a public launch:** the boundary depiction should be formally checked against the Survey of India's official map. LGD is a government source and the outline looks correct, but it hasn't been formally checked.

### Basemap (street tiles)
- National and state views use **no third-party tiles**: only our LGD boundaries on a plain background.
- From district zoom (Leaflet zoom ≥ 8), **OpenStreetMap standard tiles** appear, greyed by CSS so colour stays reserved for scores. The OSM Tile Usage Policy allows light use with attribution, which suits development and a pilot. **A public launch needs its own or a commercial tile provider.** OSM tiles also draw OSM's own border lines near disputed areas at high zoom.
- CARTO basemaps were the original plan but now require an API key, so they weren't used.

## 4. Assigning a measurement to regions (Phase 2+)

1. The phone turns the GPS position into a geohash-7 block **on the device** and sends only that code.
2. The server decodes the block's **centre point** and finds which district polygon contains it. Shapely's STRtree spatial index makes this fast.
3. The measurement stores `cell_id` plus `state_code`, `district_code` and `city_code`.
4. If a block straddles a boundary, it's assigned by its centre point. This is a documented approximation, at most ~100 m off (half a block's diagonal).

## 5. Aggregation per level

| Level | Computed from | Shown when |
|---|---|---|
| Block / Neighbourhood | Individual measurements in that cell (or its geohash-6 parent) | ≥ 5 tests |
| City | Measurements tagged with that city | ≥ 20 tests in ≥ 3 neighbourhoods |
| District | Measurements tagged with that district | ≥ 30 tests in ≥ 5 neighbourhoods |
| State/UT | Measurements tagged with that state | ≥ 100 tests in ≥ 15 neighbourhoods across ≥ 3 districts |
| India | All measurements | ≥ 300 tests in ≥ 40 neighbourhoods across ≥ 8 districts |

These rules live in `backend/services/stats.py` (`RULES`) and are tested in `tests/unit/test_stats.py`. Example: 400 tests all in Bengaluru would score Bengaluru, but leave Karnataka "Not enough tests", because they cover only one district. Only tests from the last 180 days count (`FRESHNESS_WINDOW_DAYS`). Providers need ≥ 5 tests in the same area (and the same time period) to be ranked.

Medians are always computed from the **underlying measurements**, never as a median of medians, which would give a misleading result. Results are cached in summary tables (`cell_stats`, `region_stats`) that are refreshed when new tests arrive.

## 6. Map zoom behaviour (implemented)

| Leaflet zoom | What's drawn |
|---|---|
| 4–7 | States (coloured only if they pass the state rule) |
| state selected | That state's districts, other states faded |
| 8+ | Greyed street tiles appear |
| 10–12 | Neighbourhood cells (geohash-6); district fills fade out |
| 13+ | Blocks (geohash-7) |

A breadcrumb (*India › Tamil Nadu › Chengalpattu › …*) shows where the user is, and tapping a level zooms back out. Only data inside the visible map area is requested.

## 7. Scaling path

SQLite with geohash prefix queries (`cell_id LIKE 'tf34%'`) handles a pilot with hundreds of thousands of tests. At national scale we'd move to PostgreSQL + PostGIS (spatial indexes, polygon queries inside the database). SQLAlchemy models are written so that's a configuration change plus a migration, not a rewrite.
