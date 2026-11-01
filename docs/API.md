# API Conventions

All JSON endpoints live under **`/api/v1/`**, and the same endpoints are also mounted at **`/api/`**, which always means "the current version". So `GET /api/health` and `GET /api/v1/health` are identical. The version number means we can change the API later (`/api/v2/`) without breaking existing pages.

## Rules

| Topic | Convention |
|---|---|
| Format | JSON in, JSON out. `Content-Type: application/json` |
| Field names | `snake_case` |
| Units | Part of the name: `download_mbps`, `latency_ms`, `jitter_ms` |
| Coordinates | Named `lat` / `lng`, WGS 84. Bounding boxes are `[south, west, north, east]` |
| Time | ISO 8601 in UTC, e.g. `2026-11-01T09:00:00Z` |
| Region codes | Case-insensitive on input (`in-tn` works), uppercase on output (`IN-TN`) |
| Lists | `{"data": [...], "meta": {"count": n}}`. Pagination (`limit` / `cursor`) is added when a list can grow large |
| Methods | `GET` reads, `POST` creates. Nothing changes data on `GET` |
| Errors | Always the envelope below, with plain-language messages that are safe to show users |

### Success envelope
```json
{ "data": { ... }, "meta": { ... } }
```

### Error envelope
```json
{
  "error": {
    "code": "invalid_parameter",
    "message": "Unknown region level.",
    "details": { "level": "Must be one of: country, state, district, city" }
  }
}
```

| HTTP status | `code` | When |
|---|---|---|
| 400 | `bad_request`, `invalid_parameter`, `validation_error`, `area_too_large` | Input is wrong |
| 404 | `not_found` | Unknown route or record |
| 405 | `method_not_allowed` | Wrong HTTP method |
| 429 | `rate_limited` | Too many requests (measurement submissions) |
| 500 | `server_error` | Bug on our side. No internal details are ever returned |
| 409 | `duplicate_submission` | That `submission_id` was already received |
| 413 | `payload_too_large` | Request body over 64 KB |
| 422 | `outside_service_area` | Test location is outside India |
| 503 | `service_unavailable` | Database unreachable |

In code, raise `ApiError(code, message, status, details)` from `backend/utils/responses.py` and return successes with `ok(data, meta)`.

## Implemented endpoints

Paths are shown without the prefix. Every one works at both `/api/…` and `/api/v1/…`.

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness and database check |
| **Measurements** | |
| `POST /measurements` | Submit a test (see below). Rate-limited to 30/hour per network, with one shared bucket for `/api` and `/api/v1` |
| `GET /measurements?area=&provider=&limit=&before=` | Recent **counted** tests, newest first (max 100 per page, `meta.next_before` for the next page). Never includes the ~150 m block. A test's ~1 km `neighbourhood` is shown only once that neighbourhood has ≥ 5 tests, otherwise `null` |
| **Map** | |
| `GET /map/states` | All 36 states/UTs with cached summaries, for the national map |
| `GET /map/districts?state=IN-TN` | That state's districts with cached summaries |
| `GET /map/cells?bbox=s,w,n,e&precision=6\|7` (also `/cells`) | Neighbourhood (6) or block (7) cells in view. Max span 4° (precision 6) or 0.6° (precision 7) |
| **Providers** | |
| `GET /providers` | The 18 listed Indian providers, with ASN count and number of counted tests |
| `GET /providers/rankings?area=` | Ranked providers in an area (default India) plus those with too few tests |
| `GET /me/provider` | Which provider *you* appear to be on. The IP is used in memory only and never stored |
| **Guided navigation** | |
| `GET /navigation/nearby?cell=<geohash-7>&radius=1500` | Up to 5 nearby blocks/neighbourhoods that score **Good**, have ≥ 5 tests, and beat the current area by ≥ 5 points. Ranked by `score − distance/50 m`. Radius 200–3000 m. Receives only the block code. Includes `notice` ("not a guarantee") |
| **Reports** | |
| `GET /export/areas.csv?area=<region>&type=children\|neighbourhoods` | CSV of **aggregates only** (status, score, band, counts, medians, last test). Never individual tests or ~150 m blocks |
| **Statistics** | |
| `GET /statistics?area=` | Headline numbers (default India): summary, neighbourhood Good/Fair/Weak distribution, coverage counts, share of tests with an identified provider, child areas with a score |
| `GET /insights?area=` | Summary, distribution, weakest and strongest neighbourhoods, providers, children |
| `GET /regions/<code>/stats` · `GET /cells/<cell>/stats` | Area detail used by the map panel |
| **Places** | |
| `GET /regions?level=&parent=` · `GET /regions/<code>` | States, districts and cities |
| `GET /search?q=` | Place search on our own data (no third-party geocoder) |
| `GET /locate?cell=<geohash-7>` | Which state, district and city a block is in. Receives only the block code |

### Filters
Area endpoints (`regions/<code>/stats`, `cells`, `cells/<cell>/stats`, `map/*`, `insights`, `statistics`, `measurements`, `navigation/nearby`, `export/areas.csv`) accept:
- `period=7|30|90|180` (days, default 180 = the full freshness window)
- `provider=<slug>|unidentified`

`providers/rankings` accepts `period` only (a provider filter makes no sense when comparing providers). Responses echo the applied filters as `filters: {period_days, provider}`. Cached summaries are used only for the default, unfiltered view.

`insights` also returns `trend` (median score per week for periods ≤ 30 days, otherwise per 30 days). Each bucket needs ≥ 5 tests, and `enough_data` is true only when ≥ 3 buckets have a score. It also returns `density` (how many tests each neighbourhood has).

`area` is a region code (`IN`, `IN-TN`, `IN-TN-D568`, `IN-TN-C1264527`) or a 6- or 7-character cell code.

### `POST /measurements`
Request:
```json
{"cell_id": "tf2cpct", "download_mbps": 38, "upload_mbps": 12, "latency_ms": 45, "jitter_ms": 8,
 "engine": "mlab-ndt7", "connection_type": "wifi"}
```
- `cell_id`: geohash-7 (~150 m), computed **on the device**. Raw coordinates are never accepted.
- `submission_id` (optional): a random lower-case UUID v4 made by the browser for each test. A repeat gets 409 instead of being counted twice.
- Speeds must be > 0 and ≤ 10,000. `latency_ms` must be > 0 and ≤ 10,000. `jitter_ms` must be ≥ 0. `engine` must be `mlab-ndt7`. `connection_type` is one of `mobile|wifi|wired|unknown`.
- Any `score`/`nqi` sent by the client is ignored. **The server calculates the NQI.**
- The server identifies the provider from the request's IP (IP → ASN), then discards the IP.

Response `201`:
```json
{"data": {"id": 1, "score": 74, "band": "good", "nqi": 74.4, "tested_at": "2026-11-01T09:00:00Z",
  "cell_id": "tf2cpct", "neighbourhood": "tf2cpc", "state_code": "IN-TN", "district_code": "IN-TN-D730",
  "city_code": null, "counted": true, "message": null,
  "provider": {"status": "identified", "provider": {"slug": "jio", "name": "Jio", "kind": "both"},
               "network": null, "counts_towards_scores": true, "message": "You appear to be using Jio."}}}
```
`counted` is `false` (with a plain-language `message`) for VPN/cloud networks and implausible values. Those results are stored but kept out of scores.

### Provider `status` values
| Status | Meaning |
|---|---|
| `identified` | ASN belongs to a provider in `backend/reference/providers.json` |
| `other_isp` | A real ISP we don't list. `network` gives its operator name |
| `vpn_or_hosting` | VPN, proxy or cloud network. The result is not counted in area scores |
| `unknown` | Private/local address, not in the database, or no database installed |

### The `summary` object
```json
{
  "status": "ok | insufficient | no_data",
  "score": 72, "band": "good | fair | weak | null",
  "sample_count": 639, "neighbourhood_count": 120, "block_count": 410, "district_count": 1,
  "last_updated": "2026-11-01T05:00:00Z",
  "medians": {"download_mbps": 43.3, "upload_mbps": 15.0, "latency_ms": 92, "jitter_ms": 20.0},
  "requirement": {"min_samples": 30, "min_neighbourhoods": 5, "min_districts": 1}
}
```
`score`, `band` and `medians` are `null` unless `status` is `ok`.

## Planned
- Aggregated CSV export for planners.
