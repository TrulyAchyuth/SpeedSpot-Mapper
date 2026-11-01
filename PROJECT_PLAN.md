# SpeedSpot Mapper — Project Plan

> **Your city. Your connection.**
> A friendly web app that helps everyday people see how good the internet really is on their street, compare providers, and find a better-connected spot nearby.

This plan is written for someone learning while building. Where a technical idea appears for the first time, a short **"In plain words"** note explains it.

---

## 1. Starting point and confirmed scope

| Item | State |
|---|---|
| Python | **3.12.16**, installed with `uv`, `.venv` recreated (3.9.6 was end-of-life) |
| Git | Default branch is **`main`**. GitHub remote: https://github.com/TrulyAchyuth/speedspot-mapper (private) |
| Specification | `SpeedSpot_Mapper_Enhanced.pptx`, 15 slides (DA2 mini project, BCSE316L Design of Smart Cities) |
| Rules | `CLAUDE.md`: design system, navigation, stack, engineering standards |
| Foundation (Phase 0) | ✅ Complete. See `PROJECT_STATUS.md` |

### Confirmed scope (updated 2026-11-01)
- **Geography: all of India**, covering 28 states and 8 union territories, with drill-down **India → State → District → City → Neighbourhood → ~150 m block**. VIT Chennai is only the first development and pilot location. Full design in [docs/GEOSPATIAL.md](docs/GEOSPATIAL.md).
- **Stack:** Python 3.12+, Flask, SQLAlchemy, SQLite (PostgreSQL/PostGIS later), HTML/CSS/JS, Leaflet, GeoJSON, Git.
- **Data:** genuine measurements only. The early development demo-data tool was removed on 2026-11-01. See [docs/DATA_INTEGRITY.md](docs/DATA_INTEGRITY.md).
- **API:** versioned under `/api/v1/` with one response envelope. See [docs/API.md](docs/API.md).

---

## 2. What the presentation asks for

### 2.1 The problem (slide 2)
- People can't see how well each provider actually performs on their street. All they have is advertising and word of mouth.
- Telecom operators keep their coverage data private, so city planners and residents never see where the weak spots are.
- Choosing a provider when you move house or travel ends up being guesswork.

### 2.2 The idea (slide 3): Measure → Map → Guide
1. **Measure:** a quick speed test in the browser (download, upload, ping, jitter).
2. **Map:** the result is placed into a grid square of about 150 m on a shared city map.
3. **Guide:** grid squares get a score and providers get ranked, and the app points people towards stronger connections.

The presentation is clear that the speed test itself isn't new. The new part is the **city lens**: a score for each neighbourhood, provider rankings per area, guidance to better spots, and data that planners can use (slide 4).

### 2.3 Scoring: the Network Quality Index (slide 7)

```
NQI = 100 × (0.40·D + 0.20·U + 0.25·L + 0.15·J)

D = min(download ÷ 50 Mbps, 1)
U = min(upload ÷ 20 Mbps, 1)
L = max(0, 1 − latency ÷ 200 ms)
J = max(0, 1 − jitter ÷ 50 ms)
```

- **Area score** = the *median* NQI of all tests in a ~150 m cell, **shown only once the cell has at least 5 tests**.
- Bands: **70–100 Good**, **40–69 Fair**, **0–39 Weak**.
- Worked example: 38 down / 12 up / 45 ms / 8 ms → D 0.76, U 0.60, L 0.775, J 0.84 → **74.4, shown as 74 (Good)**. I checked this by hand, and it will become our first automated test.

> **In plain words: why the median?** Line up all the scores in a cell and take the middle one. If one person's phone glitches and reports 0, or someone fakes 1000, the middle value barely changes. An average would be pulled around by those outliers.

### 2.4 Full requirements list

Each requirement gets an ID so we can track it in `PROJECT_STATUS.md`.

**Measurement**
| ID | Requirement | Source |
|---|---|---|
| M1 | In-browser download speed test | Slides 3, 6, CLAUDE.md |
| M2 | Upload speed test | Slides 3, 6 |
| M3 | Latency (ping) | Slides 3, 6 |
| M4 | Jitter (how much the ping varies) | Slides 3, 6 |
| M5 | Run against **external** test servers so we measure the user's connection, not our own server's | Slide 5 |
| M6 | Animated speedometer display (SVG), with motion turned off for users who prefer reduced motion | Slides 5, 6, 13 |
| M7 | Never invent or simulate measurement values | CLAUDE.md |

**Location and privacy**
| ID | Requirement | Source |
|---|---|---|
| L1 | Browser geolocation, **only with explicit consent** | Slides 5, 12, CLAUDE.md |
| L2 | Snap the location to a ~150 m grid cell (geohash) | Slides 3, 5, 6 |
| L3 | Store only the grid cell, **never raw GPS coordinates or IP addresses** | Slides 5, 12 |
| L4 | Follow the principles of India's DPDP Act 2023 (consent, purpose limitation, data minimisation) | Slide 12 |

**Provider identification**
| ID | Requirement | Source |
|---|---|---|
| P1 | Work out the provider from the IP address (IP → ASN lookup) | Slides 5, 6, 12 |
| P2 | Throw away the IP address right after the lookup | Slide 5 |
| P3 | Show friendly provider names ("Jio", not "AS55836 Reliance Jio Infocomm Ltd") | CLAUDE.md philosophy |

**Map and aggregation**
| ID | Requirement | Source |
|---|---|---|
| G1 | Interactive Leaflet map of the city | Slides 5, 13 |
| G2 | Crowd-sourced coverage layer (grid cells coloured by score, optional heatmap) | Slides 5, 6 |
| G3 | Score per cell = median NQI, shown only when there are 5 or more samples | Slide 7 |
| G4 | Good / Fair / Weak bands | Slide 7 |

**Comparison, guidance and insights**
| ID | Requirement | Source |
|---|---|---|
| C1 | Rank providers per area by median NQI once there is enough data | Slide 6 |
| N1 | Find the nearest strong-score cell and show its distance and direction | Slide 6 |
| N2 | Walking route to that cell | Slide 6 |
| I1 | City planner analytics: weak areas, data coverage, provider comparison | Slides 4, 9, 10 |
| I2 | Planner-ready data export (aggregated, never raw) | Slides 4, 9 |

**Security and reliability**
| ID | Requirement | Source |
|---|---|---|
| S1 | Validate all input on the server | Slides 5, 12 |
| S2 | Rate limiting (per device and per network) | Slides 5, 12 |
| S3 | Filter outliers and extreme values | Slide 12 |
| S4 | API protection (tokens or origin checks) before any public launch | Slides 12, 13 |
| S5 | HTTPS in deployment (browsers require it for GPS) | Slide 13 |
| S6 | Keep secrets out of source control | CLAUDE.md |

**User experience** (from CLAUDE.md and your brief)
| ID | Requirement |
|---|---|
| U1 | Five-item navigation: Home, Explore Map, Speed Test, Compare Providers, Insights |
| U2 | Mobile-first, responsive, works on any modern browser with no install |
| U3 | Plain language, no jargon on public pages |
| U4 | Accessible to elderly users and people using screen readers (WCAG 2.2 AA target) |
| U5 | Design system: the five specified colours, rounded cards, subtle shadows, generous whitespace |

### 2.5 Explicitly *not* in the first version (slide 8, future scope)
The presentation is honest that these need much more data or a native app, so we will **not** claim them:
historical trend charts, smart alerts, automatic PDF reports, weak-zone prediction (IDW/kriging), congestion forecasting, dynamic re-routing, signal strength in dBm (browsers can't read it), suggestions for tower gaps using OpenCelliD, ward-level admin dashboards with login, and PostgreSQL/PostGIS.

The architecture below leaves room for them so they can be added later without a rewrite.

---

## 3. Product design: what users will see

### 3.1 Plain-language vocabulary

Public pages use friendly words. The technical term appears only in small "Learn more" text.

| Technical term | What users see |
|---|---|
| Download speed (Mbps) | **Download**: how fast things load |
| Upload speed | **Upload**: how fast you can send photos and video |
| Latency / ping | **Response time**: how quickly the internet reacts |
| Jitter | **Stability**: how steady your connection is (important for calls) |
| Network Quality Index | **Connection Score** (out of 100) |
| ASN / ISP | **Provider** |
| Geohash cell | **Area** or **block** |
| Sample count | "Based on 12 tests" |

### 3.2 The five pages

1. **Home:** slogan, a large "Test my connection" button, a small "Explore the map" link, and three-step "How it works" cards (Measure → Map → Guide). Calm, lots of whitespace.
2. **Speed Test:** one large button. Before the test runs, a short consent card explains what happens and lets the user choose "Add my result to the community map" (location requested) or "Just test, don't share". A speedometer animates while the test runs. Results appear as a score card with plain-language verdicts such as "Great for video calls" or "May struggle with HD streaming".
3. **Explore Map:** a full-screen map with a soft, light basemap. Grid squares are coloured Good, Fair, Weak or "Not enough tests yet". Tapping a square opens a bottom sheet (a panel that slides up from the bottom on phones) with its score, number of tests and best provider there. Also includes a **"Find better signal near me"** button and a "Locate me" button.
4. **Compare Providers:** cards ranking providers for "Near me" or "Whole city", showing median score, typical download speed and number of tests. When there isn't enough data, the page says so plainly.
5. **Insights:** for city planners and curious residents. Summary numbers, a weakest-areas list, a provider comparison chart, how much of the city has data, and **CSV download of aggregated data**.

There will also be a **Privacy** page, linked from the footer and the consent card, explaining exactly what we store.

### 3.3 Colour and accessibility

I checked the CLAUDE.md colours for contrast. Contrast is how readable text is against its background, and WCAG requires **4.5 : 1** for normal text.

| Combination | Ratio (approx.) | Verdict |
|---|---|---|
| Deep forest `#263B32` on off-white `#F7F8F5` | ~11 : 1 | Excellent for all text |
| Natural green `#638B72` on off-white | ~3.6 : 1 | **Not enough for body text.** Fine for icons, borders and large headings |
| White on natural green `#638B72` | ~3.8 : 1 | **Not enough for normal button text.** Fine for large, bold text |

**Decision:** body text and primary buttons use deep forest. Natural green is for accents, icons, large text and the "Good" colour. Score colours (Good / Fair / Weak) will **always come with a text label and an icon**, so colour-blind users don't have to rely on colour alone. Fair and Weak will use muted amber and muted terracotta (no neon), with exact values chosen and contrast-checked in Phase 0.

Other accessibility commitments: base font size of at least 16 px with a larger option, touch targets of at least 44 × 44 px, full keyboard navigation, screen-reader labels on the map and speedometer, and `prefers-reduced-motion` respected.

---

## 4. Software architecture

### 4.1 The big picture

```
┌─────────────────────────── User's browser (phone or laptop) ───────────────────────────┐
│                                                                                       │
│  Pages (HTML/CSS/JS)     Speed-test engine ─────────────► External test servers       │
│  Leaflet map             (runs in browser)                (M-Lab or Cloudflare)       │
│  Geolocation (consent)                                                               │
│     │                                                                                 │
│     │ exact GPS position ──► converted to a ~150 m cell ID *on the device*             │
│     │                         (exact position never sent to our server)              │
└─────┼─────────────────────────────────────────────────────────────────────────────────┘
      │  HTTPS JSON:  { cell: "tf34e2k", download: 38.2, upload: 12.1, latency: 45, jitter: 8 }
      ▼
┌─────────────────────────────── Flask server (our code) ───────────────────────────────┐
│  routes/      → receive requests, check rate limits, validate input                   │
│  services/    → asn_lookup (IP → provider, local database file, IP then discarded)     │
│                 nqi (score formula)                                                   │
│                 aggregation (median per cell, per provider, ≥ 5 rule)                 │
│                 insights (planner statistics, CSV export)                             │
│  models/      → SQLAlchemy tables                                                     │
│     │                                                                                 │
│     ▼                                                                                 │
│  SQLite database file (instance/speedspot.db)                                         │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

> **In plain words: frontend and backend.** The *frontend* is everything that runs in your browser: the pages, the map and the speed test. The *backend* is our Python program on a server. It receives results, stores them and calculates scores. They talk using small text messages in a format called JSON, through addresses called the *API* (for example `POST /api/v1/measurements`).

### 4.2 Key architectural decisions (and why)

| # | Decision | Why |
|---|---|---|
| D1 | **Flask "application factory"** (`create_app()`) with **Blueprints** for each feature | Standard Flask structure. Tests can create a fresh app with a temporary database, and features stay in separate files. |
| D2 | **Server-rendered pages (Jinja templates) plus plain JavaScript modules**, with no React and no build step | Matches the required stack. It is easier to learn, faster to load on cheap phones, and has nothing extra to compile. |
| D3 | **The speed test runs in the browser against external servers** | Required by M5. If we tested against our own server, we'd be measuring our hosting company's bandwidth instead of the user's internet. |
| D4 | **The grid cell is computed on the user's device**, and only the cell ID is sent | Stronger privacy than the slide's design: the exact location never reaches our server. The server still checks that the cell ID is valid and inside our service area. |
| D5 | **Geohash precision 7** for the grid | A geohash-7 cell is about **153 m × 153 m** at the equator (about 149 m × 153 m around 13° N), which matches the "~150 m" requirement closely. |
| D6 | **The IP → provider lookup uses a database file stored on our server** (not an online API) | The user's IP never leaves our server, there's no API key to leak, and there are no rate limits. The IP is used once in memory and never stored or logged. |
| D7 | **Store each individual test (minus identity), plus a cached summary per cell** | Raw tests let us recalculate if the formula changes. The summary table keeps the map fast. When a test arrives, only that cell's summary is recalculated. |
| D8 | **Measurements are never fabricated.** Demo data, if used for development, is flagged `source='demo'` and excluded from all public views by default | Required by CLAUDE.md. Prevents fake numbers from ever being presented as real. |
| D9 | **Guided navigation is calculated in the browser** | The browser already has the user's position and the list of nearby good cells, so it can work out the nearest one itself. The user's live location never has to be sent to us. |
| D10 | **Walking directions are handed off to Google Maps (or OpenStreetMap) via a link** first, with an in-app route as an optional later step | It's free, needs no API key, and is familiar to everyone. In-app routing needs a third-party API key and would send the user's location to that service. |
| D11 | **Grid squares, not a blurry heatmap, are the main map layer** | Squares are honest ("this block, 12 tests") and easy to tap. A heatmap blur can suggest data where none exists. A heatmap can be an optional toggle. |
| D12 | **SQLite now, written so PostgreSQL can replace it later** | SQLAlchemy hides most database differences. Switching becomes mostly a configuration change (slides 13 and 14). |
| D13 | **Third-party JS libraries are pinned and stored in the project ("vendored")** | Pinning means using one exact version. The app keeps working if a CDN changes, and a strict security policy (CSP) can be used. The speed-test engine also needs its worker scripts on our own domain. |

### 4.3 Data model (database tables)

```
providers                       provider_asns
─────────                       ─────────────
id                              asn (e.g. 55836)        ──► provider_id
slug        ("jio")             provider_id
name        ("Jio")
kind        (mobile/broadband/both)

measurements  (one row per test — no IP, no GPS, no device ID)
────────────
id
created_at        (rounded to the hour, for privacy)
cell_id           (geohash-7, e.g. "tf34e2k")
download_mbps, upload_mbps, latency_ms, jitter_ms
nqi               (0–100, calculated on the server, never trusted from the browser)
provider_id       (nullable — "Unknown provider" if lookup fails)
asn               (the network number; identifies a company, not a person)
connection_type   (optional, user-chosen: "Mobile data" / "Wi-Fi" / "Not sure")
engine            ("mlab-ndt7" or "cloudflare"), engine_version
source            ("user" or "demo")
flagged           (true if outlier rules triggered; excluded from scores)

cell_stats  (cached summary, rebuilt for one cell whenever it gets a new test)
──────────
cell_id, sample_count, median_nqi, median_download, median_upload,
median_latency, median_jitter, band (good/fair/weak/none), updated_at

cell_provider_stats  (same idea, per provider per cell)
───────────────────
cell_id, provider_id, sample_count, median_nqi, median_download
```

> **In plain words: ORM.** SQLAlchemy lets us describe tables as Python classes (`class Measurement(db.Model)`) and query them with Python instead of writing SQL text by hand. It also protects us from *SQL injection*, a common attack where malicious text gets run as a database command.

### 4.4 API design (first version)

| Method & path | Purpose |
|---|---|
| `GET /api/v1/health` | Is the server alive? (used by tests and hosting) |
| `GET /api/v1/me/provider` | "You appear to be on **Jio**". Looks up the provider from the IP and returns only the name. |
| `POST /api/v1/measurements` | Submit a test result: cell ID plus four numbers. Returns the calculated score. |
| `GET /api/v1/cells?bbox=…` | Cell summaries inside the visible map area (scores only where there are 5 or more samples) |
| `GET /api/v1/cells/<cell_id>` | Details for one cell, including its provider breakdown |
| `GET /api/v1/providers/rankings?scope=city\|near&cell=…` | Provider rankings |
| `GET /api/v1/insights/summary` | Planner headline numbers |
| `GET /api/v1/insights/weak-areas` | Weakest cells with enough data |
| `GET /api/v1/insights/export.csv` | Aggregated per-cell CSV (no individual tests) |

---

## 5. Proposed folder structure

This is the target structure. The parts that exist after Phase 0 are listed in `PROJECT_STATUS.md`. Differences from the tree below: the API is versioned (`routes/api.py` serves `/api/v1`), and `backend/reference/` holds committed reference data such as the states and UTs list.

```
speedspot-mapper/
├── CLAUDE.md                      # project rules (not modified)
├── PROJECT_PLAN.md                # this file
├── PROJECT_STATUS.md              # progress log, updated after every phase
├── README.md                      # how to install and run
├── SpeedSpot_Mapper_Enhanced.pptx # original specification
├── .gitignore                     # keeps .venv, .env, databases and data files out of git
├── .env.example                   # template for secrets (the real .env is never committed)
├── requirements.txt               # exact library versions the app needs
├── requirements-dev.txt           # extra tools for testing
├── run.py                         # start the development server
├── wsgi.py                        # entry point for production server (gunicorn)
│
├── backend/                       # the Python package (our Flask app)
│   ├── __init__.py                # create_app() — the application factory
│   ├── config.py                  # settings for development / testing / production
│   ├── extensions.py              # shared objects: database, rate limiter
│   ├── models/
│   │   ├── __init__.py
│   │   ├── provider.py            # Provider, ProviderASN
│   │   ├── measurement.py         # Measurement
│   │   └── stats.py               # CellStats, CellProviderStats
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── pages.py               # the 5 HTML pages + Privacy
│   │   ├── api_measurements.py    # POST /api/v1/measurements, GET /api/v1/me/provider
│   │   ├── api_map.py             # /api/cells
│   │   ├── api_providers.py       # /api/providers/rankings
│   │   └── api_insights.py        # /api/insights/*
│   ├── services/
│   │   ├── nqi.py                 # the scoring formula + bands
│   │   ├── aggregation.py         # medians, ≥5 rule, cache rebuild
│   │   ├── asn_lookup.py          # IP → ASN using local database file
│   │   ├── providers.py           # ASN → friendly provider name
│   │   └── insights.py            # planner statistics, CSV
│   └── utils/
│       ├── geohash.py             # encode/decode/neighbours/bounds (small, fully tested)
│       ├── validation.py          # checks on incoming data
│       └── client_ip.py           # safely read the visitor's IP (behind proxies)
│
├── frontend/
│   ├── templates/                 # Jinja HTML templates
│   │   ├── base.html              # shared layout: header, nav, footer
│   │   ├── home.html
│   │   ├── map.html
│   │   ├── speedtest.html
│   │   ├── providers.html
│   │   ├── insights.html
│   │   └── privacy.html
│   └── static/
│       ├── css/
│       │   ├── tokens.css         # colours, spacing, radii, shadows (design system)
│       │   ├── base.css           # typography, layout, nav
│       │   └── components.css     # cards, buttons, gauges, bottom sheet
│       ├── js/
│       │   ├── api.js             # small helper for calling our API
│       │   ├── geohash.js         # same algorithm as backend, tested against same examples
│       │   ├── speedtest.js       # wraps the speed-test engine
│       │   ├── gauge.js           # SVG speedometer
│       │   ├── map.js             # Leaflet map + cell layer
│       │   ├── navigate.js        # nearest good cell, distance, direction
│       │   ├── providers.js
│       │   └── insights.js
│       ├── assets/                # icons (SVG), logo
│       └── vendor/                # pinned copies of Leaflet, speed-test client, Chart.js
│
├── data/                          # (git-ignored) downloaded IP→ASN database file
├── instance/                      # (git-ignored) SQLite database lives here
├── scripts/
│   ├── download_asn_db.py         # fetches/updates the IP→ASN database
│   ├── seed_providers.py          # loads the curated provider/ASN list
│   └── seed_demo_data.py          # DEV ONLY — clearly marked demo data
│
├── tests/
│   ├── conftest.py                # shared test setup (temporary app + database)
│   ├── unit/                      # nqi, geohash, aggregation, validation, asn
│   ├── integration/               # API endpoints through Flask's test client
│   └── e2e/                       # real browser tests with Playwright
│
└── docs/
    ├── ARCHITECTURE.md
    ├── API.md
    ├── PRIVACY.md
    ├── TESTING.md
    └── decisions/                 # short notes on major decisions ("ADRs")
```

---

## 6. External services and their limitations

> **In plain words:** an *external service* is anything our app depends on that we don't run ourselves. Each has rules, limits and privacy implications, and we need to know them before relying on them. Details marked *(verify)* will be confirmed against the provider's current documentation when we reach that phase. I won't treat them as fact before then.

### 6.1 Speed-test engine (the most important choice)

| | **M-Lab ndt7** (presentation's first choice) | **Cloudflare speed test library** | **LibreSpeed** |
|---|---|---|---|
| What it is | Open measurement platform run by Measurement Lab, with an official JavaScript client (`ndt7-js`) | Cloudflare's open-source browser library (`@cloudflare/speedtest`), which uses `speed.cloudflare.com` | Open-source test that you host yourself |
| Measures | Download and upload, plus TCP round-trip data. **Jitter has to be calculated** from RTT samples or extra pings | Download, upload, latency and jitter directly | All four |
| Servers | Global network, nearest server picked automatically by the M-Lab Locate API | Cloudflare's global network | **Our own server**, which breaks requirement M5 unless we pay for good hosting |
| Cost / keys | Free, no key | Free, no key | Free software, but we pay for the bandwidth |
| ⚠️ Privacy | **M-Lab publishes every test result as open data, including the tester's IP address** *(verify)*. Users must be told this before the test | Covered by Cloudflare's privacy policy, not published openly *(verify terms for third-party embedding)* | Data stays with us |
| Limits | Fair use, and tests take about 10 s per direction | Fair use, terms less explicitly documented for embedding *(verify)* | Limited by our hosting bandwidth |

**Recommendation:** start Phase 3 with a short **"spike"** (a small throwaway experiment) that runs both M-Lab and Cloudflare on your real Wi-Fi and mobile data, compared against a well-known reference test. Then we pick one and record why in `docs/decisions/`. Our code wraps the engine behind one `runSpeedTest()` function, so switching later is easy. LibreSpeed is not recommended because self-hosting measures our server instead of the user's connection.

### 6.2 IP → provider (ASN) lookup

> **In plain words:** every internet provider owns blocks of IP addresses, grouped under an **ASN** (Autonomous System Number). For example, Jio's main ASN is 55836. If we know your IP, we can look up which ASN it belongs to, and therefore which provider you're using. Browsers aren't allowed to tell websites your carrier name, so this is how we work it out.

| Option | Notes |
|---|---|
| **DB-IP "IP to ASN Lite"** (downloadable `.mmdb` file) | Free, CC-BY 4.0 licence (attribution required), monthly updates, no account needed *(verify)* |
| **IPinfo Lite** (downloadable) | Free, needs a free account/token, CC-BY-SA licence *(verify)* |
| **MaxMind GeoLite2 ASN** | Free account and licence key required, attribution required, and the licence requires regular updates *(verify)* |
| Online APIs (ipinfo.io, ipapi, etc.) | **Not recommended**: they send every user's IP to a third party and have rate limits |

**Recommendation:** use a downloadable database (DB-IP Lite first, since it needs no account), read it with the `maxminddb` Python library, and add a curated **ASN → friendly name** table for the major Indian providers (Jio, Airtel, Vi, BSNL, ACT and others). Every ASN in that table will be verified, not guessed.

**Known limitations, which we'll show honestly in the UI:**
- On a **VPN**, the app sees the VPN company, not the real provider.
- Some providers use several ASNs, and some small local ISPs resell bigger networks, so a result may say "Unknown provider".
- During **local development** your IP is `127.0.0.1`, which has no provider. We'll add a development-only override for testing.
- A browser can't reliably tell whether a phone is on **Wi-Fi or mobile data**, so we'll offer an optional "How are you connected?" choice.

### 6.3 Map tiles (the background map images)

| Option | Notes |
|---|---|
| **CARTO Positron** (light, minimal style) | Matches the soft, minimal look. Free for non-commercial use with attribution, within monthly view limits *(verify)* |
| **OpenStreetMap standard tiles** | Free, attribution required, under a usage policy meant for light use, not heavy traffic |

**Recommendation:** CARTO Positron for the look, with OpenStreetMap as a fallback. Attribution is always visible, as required.

### 6.4 Walking directions

| Option | Notes |
|---|---|
| **Link to Google Maps / OpenStreetMap directions** | Free, no key, familiar, and the user's location isn't sent to us. **Recommended for the MVP.** |
| OpenRouteService API | Free key with a daily request limit *(verify)*. Gives an in-app route line, but sends the user's location to ORS through our server. Optional later. |
| OSRM public demo server | Demo use only, not for production |

### 6.5 Hosting and HTTPS (later phase)

- Browsers only allow GPS on **HTTPS** sites, or on `localhost` during development.
- To test on your phone before deployment, we'll use a temporary HTTPS tunnel (for example Cloudflare Tunnel).
- **Render** (named in the slides): the free tier sleeps when idle, and **its disk is wiped on every redeploy, which would erase a SQLite database** *(verify)*. We'll need a paid persistent disk, a different host (for example PythonAnywhere), or a move to managed PostgreSQL. We'll decide at the deployment phase.

### 6.6 Optional future data sources
- **M-Lab open data** (BigQuery): its locations come from IP addresses and are only city-level, so it's **not suitable for 150 m cells**. At most it could support city-level provider statistics, clearly labelled.
- **OpenCelliD** tower locations: free API key, CC-BY-SA licence, rate-limited. Future "tower gap" feature only.

---

## 7. Privacy and security requirements

### 7.1 Privacy: what we collect and what we don't

| Data | Collected? | Detail |
|---|---|---|
| Exact GPS position | **Never sent to our server** | Turned into a ~150 m cell ID on the device (D4) |
| ~150 m cell ID | Yes, **only if the user opts in** | Without consent, the test still works but the result isn't added to the map |
| IP address | **Used for a moment, never stored or logged** | Only to find the provider. Production logs are set up to leave IPs out |
| Provider / ASN | Yes | Identifies a company, not a person |
| Speed results | Yes | The four numbers plus the calculated score |
| Time of test | Yes, **rounded to the hour** | Makes it harder to link a test to a specific person |
| Accounts, names, emails | **No** | No sign-up needed |
| Cookies / trackers / analytics | **No third-party trackers** | Only strictly necessary storage |
| Device identifier | **Not stored** | Rate limiting keeps short-lived counters in memory only |

**Additional privacy rules**
- **Consent first:** a clear, friendly consent card before any location request. "Don't share" is just as easy to pick as "Share". Consent is asked per test, and the user's choice can be remembered on their device.
- **Small-number protection:** cells with fewer than 5 tests show "Not enough tests yet" instead of a score. In a quiet area, a single result could otherwise be linked back to a household.
- **Third-party disclosure:** if we pick M-Lab, the consent card explains in plain words that M-Lab publishes test results, including IP addresses, as open research data.
- **GPS accuracy check:** if the browser reports the location is only accurate to, say, 500 m, we won't place the result in a 150 m cell. We'll say why, kindly.
- **Privacy page:** explains everything above in simple language, in line with DPDP Act 2023 principles (notice, consent, purpose limitation, data minimisation).

### 7.2 Security

| Risk | Protection |
|---|---|
| Fake or junk submissions | Server-side validation (types, sensible ranges such as 0–10,000 Mbps), outlier flagging, median scoring, rate limits, and the ≥ 5 samples rule |
| Spam / flooding | `Flask-Limiter` rate limits per network on submission endpoints |
| Fake scores | The server **recalculates** the score itself and ignores any score the browser sends |
| SQL injection | Every query goes through the SQLAlchemy ORM (parameterised) |
| Cross-site scripting (XSS) | Jinja auto-escaping, `textContent` instead of `innerHTML` in JS, strict Content-Security-Policy |
| Cross-site request forgery | JSON-only API, `Origin` header check, SameSite cookies |
| Leaked secrets | `.env` file (git-ignored), `.env.example` committed with placeholders, and `SECRET_KEY` never hard-coded |
| Spoofed IP headers behind a proxy | `ProxyFix` set up only for the exact number of proxies in deployment |
| Clickjacking / sniffing | Security headers (`X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`) |
| Outdated libraries | Pinned versions in `requirements.txt`, checked with `pip-audit` |
| Debug mode in production | `DEBUG` forced off in the production config, checked by a test |

**Honest limitation:** a speed test runs in the user's browser, so a determined attacker could send made-up numbers directly to our API. We can make this harder, but we can't make it impossible without native apps or server-side verification. Medians, minimum sample counts, rate limits and outlier rules reduce the impact. API tokens (S4) come before a public launch.

---

## 8. Phased development roadmap

Each phase ends with something working, tests passing, and an updated `PROJECT_STATUS.md`. I'll pause for your review at the end of each phase.

### Phase 0: Foundations ✅ complete (2026-11-01)
- Python 3.12 venv, `main` branch, `.gitignore`, `.env.example`, `README.md`, `requirements*.txt`.
- App factory, config classes, `/api/v1` with response envelope, friendly errors, security headers.
- Design tokens and components, 5-item responsive navigation, honest placeholder pages, Privacy page.
- `regions` model with India + 28 states + 8 UTs, `flask init-db`, region API.
- Docs: architecture, API, geospatial, design system, demo-data strategy. 38 passing tests.

> **Update 2026-11-01, frontend milestone:** the frontend and India-wide map were built ahead of the original order. That pulled in the core logic from Phase 1, the measurement API (without provider detection) from Phase 2, the Speed Test page (Phase 3), the map (Phase 4), Compare Providers (Phase 5) and most of Insights (Phase 7). See `PROJECT_STATUS.md` for exactly what's done and what remains.

### Phase 1: Core logic (no UI)
- `nqi.py` (formula, bands, rounding) with the slide 7 worked example as a test.
- `geohash.py` (encode, decode, bounds, neighbours) tested against published reference values.
- `aggregation.py` (median, ≥ 5 rule, outlier rules).
- `validation.py`.
- Database models and table creation (`measurements` with a `source` column, `cell_stats`, `providers`).
- Demo-data commands `flask demo-data seed|clear`, gated by `ALLOW_DEMO_DATA` (see docs/DEMO_DATA.md).
- **Done when:** all core rules have unit tests and pass.

### Phase 2: Measurement API and provider detection
- `POST /api/v1/measurements` with validation, server-side scoring and cell cache updates.
- `scripts/download_asn_db.py`, `asn_lookup.py`, curated provider table, `GET /api/v1/me/provider`.
- Rate limiting, privacy-safe logging (no IPs).
- **Done when:** integration tests prove a valid submission is stored correctly, bad input is rejected, **no IP or coordinates appear in the database or logs**, and rate limits trigger.

### Phase 3: Speed Test page
- **Spike:** compare M-Lab and Cloudflare on real networks, then record the decision.
- Vendor the chosen engine, `speedtest.js` wrapper, SVG gauge, plain-language results card.
- Consent card, geolocation, GPS accuracy check, on-device geohash, submit to API.
- "Test only, don't share" path.
- Friendly error states (offline, location denied, test failed).
- **Done when:** real tests on your laptop and phone produce believable numbers (compared with a reference test on the same network) and appear in the database. Browser tests cover the consent and error flows.

### Phase 4: Explore Map (national drill-down)
- **Boundary import first:** choose a state/district boundary source that matches the Survey of India's official depiction (release blocker), add LGD district codes, simplify to per-state GeoJSON, fill region bounding boxes, and assign each measurement to its state, district and city by point-in-polygon. See docs/GEOSPATIAL.md.
- Zoom-dependent layers: states → districts → neighbourhood cells (geohash-6) → blocks (geohash-7), with a breadcrumb.
- Leaflet with the light basemap, cell squares coloured by band, legend, "Not enough tests yet" state.
- Tap a cell to open a bottom sheet with details. "Locate me" button.
- Only loads cells in the visible area (`bbox`), so it stays fast.
- **Done when:** the map shows real submitted data correctly on phone and desktop, and the API and browser tests pass.

### Phase 5: Compare Providers
- Rankings for "Near me" and "Whole city", with minimum-sample rules and clear "not enough data" messages.
- **Done when:** rankings match hand-calculated expectations in tests.

### Phase 6: Guided navigation
- "Find better signal near me": nearest Good cell, distance, simple direction ("about 300 m north-east"), and a line on the map.
- "Walk there" button that opens Google Maps or OpenStreetMap walking directions.
- **Done when:** unit tests cover distance and direction maths, and a manual test on a phone works end to end.

### Phase 7: Insights (city planner analytics)
- Headline numbers, weakest areas, provider comparison chart, data coverage, NQI distribution.
- CSV export of **aggregated** per-cell data only.
- **Done when:** the numbers match test fixtures, and the CSV contains no individual tests.

### Phase 8: Polish, accessibility and performance
- Accessibility audit (automated axe checks plus keyboard and screen-reader pass), contrast check of the final palette.
- Empty, loading and error states everywhere. Privacy page wording.
- Performance check on a slow 3G profile, and image and JS size review.
- **Done when:** there are no serious accessibility violations and the core pages load quickly on a simulated slow phone.

### Phase 9: Security hardening and deployment
- Security headers and CSP, ProxyFix, API protection (S4), `pip-audit`, production logging.
- Choose a host (see §6.5), set up HTTPS and environment secrets, deploy.
- **Done when:** the live site works on real phones over HTTPS and the security checklist passes.

### Phase 10: Campus pilot (Stage 1 from slide 14)
- QR-code invitation and collecting real tests.
- Validate NQI thresholds against real data, and fix whatever real users struggle with.
- Replace the placeholder numbers on the presentation's impact slide with real figures.

### Later (Stages 2–3, not committed)
PostgreSQL/PostGIS, planner login, historical trends, alerts, reports, prediction, native Android app for signal strength, OpenCelliD tower-gap analysis.

---

## 9. How the application will be tested

> **In plain words:** an *automated test* is a small program that checks our program. Example: "the score for 38/12/45/8 must be 74". We run all tests with one command (`pytest`) after every change. If something breaks by accident, we find out immediately.

| Level | What it checks | Tools | Examples |
|---|---|---|---|
| **Unit tests** | One small piece of logic in isolation | `pytest` | NQI worked example = 74. Values above the cap give exactly 1.0. Median of an even count. Fewer than 5 samples means no score. Geohash encode/decode against reference values. Validation rejects negative speeds |
| **Integration tests** | API endpoints with a real temporary database | `pytest` + Flask test client + in-memory SQLite | A valid POST is stored and the cell cache updates. Bad JSON returns a 400 error with a friendly message. Rate limit returns 429. **Privacy test: no IP or lat/lon is saved anywhere.** CSV export has no individual rows |
| **Provider lookup tests** | ASN mapping | A small test `.mmdb` fixture and known IPs | A known Jio IP range maps to "Jio". Private IPs map to "Unknown" |
| **JavaScript logic tests** | Browser-side maths | Run in a real browser via Playwright | JS geohash gives the same answers as Python. Distance and direction calculations |
| **End-to-end (E2E) tests** | Real browser clicking through the real app | Playwright (`pytest-playwright`) | Consent → test → result card. Location denied leads to a friendly message. Map loads cells. Nav works on phone-sized screens. *The speed-test engine is replaced by a clearly fake stand-in **in tests only**, so tests don't depend on the internet. Those numbers never reach the real database.* |
| **Accessibility tests** | Usability for everyone | axe-core via Playwright, manual keyboard and screen-reader checks (VoiceOver) | No critical violations, every button labelled, focus visible |
| **Speed-test accuracy** | Are our numbers believable? | Manual comparison | Same device and network, back to back with a reference test, repeated several times, with results recorded in `docs/TESTING.md` |
| **Manual device testing** | Real-world feel | Your phone + laptop, Chrome, Safari, Firefox | Checklist per phase in `docs/TESTING.md` |
| **Security checks** | Known weaknesses | `pip-audit`, header check, manual malicious-input tests | |

**Rule:** a feature is only marked "working" in `PROJECT_STATUS.md` once its tests pass **and** it's been tried manually. Anything else is listed as "untested" or "known issue".

---

## 10. Development workflow

- **Git:** one branch per phase (`phase-1-core-logic` …), merged into `main` when the phase is approved. Small, clearly described commits.
- **GitHub:** private repository https://github.com/TrulyAchyuth/speedspot-mapper, created and pushed on 2026-11-01 with the owner's go-ahead. Nothing is pushed without the owner's say-so.
- **Documentation:** `PROJECT_STATUS.md` after every phase, `docs/` updated alongside code, and short decision notes for big choices.

---

## 11. Main risks

| Risk | Impact | Plan |
|---|---|---|
| Not enough users (cold start) | Map looks empty, rankings say "not enough data" | Campus pilot with QR codes. Friendly empty states ("Be the first to test here!") instead of fake data |
| Speed-test engine terms or behaviour change | Test stops working | Engine wrapped behind one function, so it can be swapped. Pinned vendored version |
| Inaccurate desktop location | Results placed in the wrong cell | GPS accuracy check, results rejected for map if too imprecise |
| Free hosting wipes SQLite | Data loss | Decide hosting carefully in Phase 9. Add a backup script |
| Scope creep (AI features, etc.) | Core features unfinished | Keep to the MVP phases. Future scope stays future |

---

## 12. Decisions

| # | Question | Decision |
|---|---|---|
| 1 | Python version | ✅ Python 3.12+ (3.12.16 installed) |
| 2 | Geographic scope | ✅ All of India, with the full hierarchy. VIT Chennai is the dev and pilot location |
| 3 | Git branch | ✅ `main`. GitHub remote: TrulyAchyuth/speedspot-mapper (private) |
| 4 | Demo data | ✅ Removed entirely (2026-11-01): genuine measurements only, enforced in the database |
| 5 | Speed-test engine | ✅ M-Lab ndt7, chosen after comparing it with Cloudflare from their own documentation and live checks. See `docs/decisions/0001-speed-test-engine.md` |
| 6 | Boundary data source | ✅ LGD (Government of India) states and districts via bharatlas, plus GeoNames cities. Formal check against the Survey of India map still recommended before launch |
| 8 | IP → provider | ✅ DB-IP ASN Lite (CC BY 4.0), a local file, with 18 providers and 34 ASNs verified against it |
| 7 | Street tiles | 🟡 OpenStreetMap tiles (light use only). CARTO now needs an API key. A public launch needs a tile provider |
