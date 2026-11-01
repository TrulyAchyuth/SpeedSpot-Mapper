"""Filters, guided navigation, trends, density and CSV export."""
import csv
import io

import pytest
from sqlalchemy import func, select

from backend.extensions import db
from backend.models import AreaStatistic
from backend.routes.api.stats import CSV_COLUMNS
from backend.utils import geohash
from tests.conftest import VIT_CHENNAI

GOOD = {"download": 90, "upload": 30, "latency": 20, "jitter": 2}     # NQI 96.9 → 97
FAIR = {"download": 20, "upload": 5, "latency": 100, "jitter": 20}    # NQI 42.5 → 43
WEAK = {"download": 3, "upload": 1, "latency": 300, "jitter": 60}     # NQI 3.4 → 3
ORIGIN = geohash.encode(*VIT_CHENNAI)
LAT, LNG = VIT_CHENNAI
NORTH_500M = (LAT + 0.0045, LNG)
NORTH_1KM = (LAT + 0.009, LNG)
NORTH_2KM = (LAT + 0.018, LNG)


# ---------- Filters ----------

@pytest.fixture
def mixed(add_tests):
    add_tests(*VIT_CHENNAI, 5, provider="airtel", age_days=1)
    add_tests(*VIT_CHENNAI, 5, provider="jio", age_days=60)
    add_tests(*VIT_CHENNAI, 2, provider=None, age_days=2)


@pytest.mark.parametrize("query,expected", [
    ("", 12), ("?period=30", 7), ("?period=7", 7), ("?period=90", 12),
    ("?provider=jio", 5), ("?provider=airtel&period=30", 5), ("?provider=unidentified", 2),
])
def test_period_and_provider_filters(client, mixed, query, expected):
    body = client.get(f"/api/regions/IN-TN/stats{query}").get_json()["data"]
    assert body["summary"]["sample_count"] == expected
    assert set(body["filters"]) == {"period_days", "provider"}


def test_filters_apply_to_cells_rankings_insights_and_lists(client, mixed):
    cells = client.get("/api/cells?bbox=12.7,80.0,13.0,80.3&precision=7&period=30").get_json()["data"]
    assert sum(c["sample_count"] for c in cells) == 7
    ranked = client.get("/api/providers/rankings?area=IN-TN&period=30").get_json()["data"]["providers"]["ranked"]
    assert [p["slug"] for p in ranked] == ["airtel"]  # jio's tests are older than 30 days
    insights = client.get("/api/insights?area=IN-TN&provider=jio").get_json()["data"]
    assert insights["summary"]["sample_count"] == 5 and insights["filters"]["provider"] == "jio"
    listed = client.get("/api/measurements?provider=airtel").get_json()["data"]
    assert len(listed) == 5


@pytest.mark.parametrize("query,status", [
    ("?period=45", 400), ("?period=abc", 400), ("?provider=nobody", 404),
])
def test_invalid_filters(client, seeded, query, status):
    assert client.get(f"/api/regions/IN/stats{query}").status_code == status


def test_rankings_reject_provider_filter(client, seeded):
    response = client.get("/api/providers/rankings?provider=jio")
    assert response.status_code == 400 and "provider" in response.get_json()["error"]["details"]


def test_filtered_views_never_pollute_the_cache(client, mixed):
    client.get("/api/map/states?period=7")
    client.get("/api/regions/IN-TN/stats?provider=jio")
    assert db.session.scalar(select(func.count(AreaStatistic.id))) == 0
    states = client.get("/api/map/states").get_json()["data"]
    assert next(s for s in states if s["code"] == "IN-TN")["summary"]["sample_count"] == 12


def test_provider_ranking_needs_five_tests_per_provider(client, add_tests):
    add_tests(*VIT_CHENNAI, 5, provider="airtel")
    add_tests(*VIT_CHENNAI, 4, provider="jio")
    providers = client.get("/api/providers/rankings?area=IN-TN").get_json()["data"]["providers"]
    assert providers["min_samples"] == 5
    assert [p["slug"] for p in providers["ranked"]] == ["airtel"]
    assert providers["ranked"][0]["sample_count"] == 5 and providers["ranked"][0]["last_updated"]
    assert [(p["slug"], p["sample_count"]) for p in providers["insufficient"]] == [("jio", 4)]


# ---------- Guided navigation ----------

def nearby(client, **params):
    query = "&".join(f"{k}={v}" for k, v in {"cell": ORIGIN, **params}.items())
    return client.get(f"/api/navigation/nearby?{query}")


def test_suggests_better_areas_closest_first(client, add_tests):
    add_tests(*VIT_CHENNAI, 5, **{f"{k}": v for k, v in WEAK.items()})
    add_tests(*NORTH_500M, 5, **GOOD)
    add_tests(*NORTH_1KM, 6, **GOOD)
    data = nearby(client).get_json()["data"]
    assert data["origin"]["current_score"] == 3 and data["origin"]["current_band"] == "weak"
    blocks = [d for d in data["destinations"] if d["level"] == "block"]
    assert [b["cell_id"] for b in blocks] == [geohash.encode(*NORTH_500M), geohash.encode(*NORTH_1KM)]
    first = blocks[0]
    assert first["score"] == 97 and first["sample_count"] == 5 and first["last_updated"]
    assert 400 < first["distance_m"] < 600 and first["walking_minutes_estimate"] >= 1
    assert "not a guarantee" in data["notice"]
    assert ORIGIN not in [d["cell_id"] for d in data["destinations"]]


def test_only_good_areas_with_enough_tests_are_suggested(client, add_tests):
    add_tests(*NORTH_500M, 4, **GOOD)        # too few tests
    add_tests(*NORTH_1KM, 5, **FAIR)         # not Good
    assert nearby(client).get_json()["data"]["destinations"] == []


def test_destination_must_beat_a_good_current_area(client, add_tests):
    add_tests(*VIT_CHENNAI, 5, download=50, upload=20, latency=30, jitter=4)   # already Good (≈ 93)
    add_tests(*NORTH_500M, 5, download=50, upload=20, latency=28, jitter=4)    # barely better
    assert nearby(client).get_json()["data"]["destinations"] == []


def test_radius_is_respected(client, add_tests):
    add_tests(*NORTH_2KM, 5, **GOOD)
    assert nearby(client, radius=1500).get_json()["data"]["destinations"] == []
    far = nearby(client, radius=3000).get_json()["data"]["destinations"]
    assert far and far[0]["distance_m"] > 1500


def test_neighbourhoods_fill_in_when_blocks_are_sparse(client, add_tests):
    # 5 good tests spread over 5 different blocks of one neighbourhood: no block qualifies alone.
    for i in range(5):
        add_tests(LAT + 0.0045, LNG - 0.0016 * i, 1, **GOOD)
    destinations = nearby(client).get_json()["data"]["destinations"]
    assert [d["level"] for d in destinations] == ["neighbourhood"]


@pytest.mark.parametrize("params", [{"cell": "tf2cp"}, {"cell": "zzzzzzz!"}, {"radius": 50}, {"radius": 9000},
                                    {"radius": "far"}])
def test_navigation_validation(client, seeded, params):
    assert nearby(client, **params).status_code == 400


def test_navigation_never_needs_coordinates(client, seeded):
    response = client.get("/api/navigation/nearby?lat=12.84&lng=80.15")
    assert response.status_code == 400


# ---------- Trends and density ----------

def test_trend_needs_three_scored_periods(client, add_tests):
    add_tests(*VIT_CHENNAI, 5, age_days=1)
    add_tests(*VIT_CHENNAI, 5, age_days=40)
    trend = client.get("/api/insights?area=IN-TN").get_json()["data"]["trend"]
    assert trend["bucket_days"] == 30 and len(trend["buckets"]) == 6
    assert trend["enough_data"] is False
    add_tests(*VIT_CHENNAI, 5, age_days=70)
    trend = client.get("/api/insights?area=IN-TN").get_json()["data"]["trend"]
    assert trend["enough_data"] is True
    assert sum(b["sample_count"] for b in trend["buckets"]) == 15
    assert [b["score"] is not None for b in trend["buckets"]].count(True) == 3


def test_short_periods_use_weekly_buckets(client, add_tests):
    add_tests(*VIT_CHENNAI, 5, age_days=2)
    trend = client.get("/api/insights?area=IN-TN&period=30").get_json()["data"]["trend"]
    assert trend["bucket_days"] == 7 and len(trend["buckets"]) == 5


def test_density_buckets(client, add_tests):
    add_tests(*VIT_CHENNAI, 3)
    add_tests(*NORTH_1KM, 6)
    add_tests(13.0827, 80.2707, 21)
    density = client.get("/api/statistics").get_json()["data"]["density"]
    assert [b["count"] for b in density["buckets"]] == [1, 1, 1]
    assert density["neighbourhoods"] == 3 and density["max_tests_per_neighbourhood"] == 21


def test_weak_zones_exclude_good_neighbourhoods(client, add_tests):
    add_tests(*VIT_CHENNAI, 5, **GOOD)
    add_tests(13.0827, 80.2707, 5, **WEAK)
    weakest = client.get("/api/insights?area=IN-TN").get_json()["data"]["weakest"]
    assert [w["band"] for w in weakest] == ["weak"]


# ---------- CSV export ----------

def read_csv(response):
    assert response.status_code == 200 and response.mimetype == "text/csv"
    return list(csv.reader(io.StringIO(response.get_data(as_text=True))))


def test_csv_by_district(client, add_tests):
    add_tests(*VIT_CHENNAI, 40, spread_cells=8)
    response = client.get("/api/export/areas.csv?area=IN-TN&period=90")
    rows = read_csv(response)
    assert rows[0] == CSV_COLUMNS
    assert rows[1][:3] == ["IN-TN", "Tamil Nadu", "state"]
    districts = rows[2:]
    assert len(districts) >= 38 and all(r[2] == "district" for r in districts)
    scored = [r for r in districts if r[3] == "ok"]
    assert len(scored) == 1 and int(scored[0][6]) == 40
    assert 'filename="speedspot-in-tn-children-90d.csv"' in response.headers["Content-Disposition"]


def test_csv_by_neighbourhood_has_aggregates_only(client, add_tests):
    rows = add_tests(*VIT_CHENNAI, 6)
    data = read_csv(client.get("/api/export/areas.csv?area=IN-TN&type=neighbourhoods"))
    body = "\n".join(",".join(r) for r in data)
    assert data[2][0] == rows[0].cell_id[:6] and data[2][6] == "6"
    assert rows[0].cell_id not in body          # never the ~150 m block
    assert "submission" not in body and "asn" not in body.lower()


def test_csv_counts_only_genuine_counted_tests(client, add_tests):
    add_tests(*VIT_CHENNAI, 5)
    add_tests(*VIT_CHENNAI, 3, flagged=True)
    data = read_csv(client.get("/api/export/areas.csv?area=IN-TN"))
    assert data[0] == CSV_COLUMNS and "includes_demo_data" not in data[0]
    assert data[1][6] == "5"


@pytest.mark.parametrize("query,status", [("?type=everything", 400), ("?area=IN-XX", 404), ("?period=11", 400)])
def test_csv_validation(client, seeded, query, status):
    assert client.get(f"/api/export/areas.csv{query}").status_code == status
