"""The area_statistics cache: hits, invalidation, expiry and concurrency."""
from datetime import timedelta

from sqlalchemy import func, select

from backend.extensions import db
from backend.models import AreaStatistic
from backend.services import stats, stats_cache
from backend.services.regions import get_region
from tests.conftest import JIO_IP, VIT_CHENNAI


def _count():
    return db.session.scalar(select(func.count(AreaStatistic.id)))


def test_summary_is_computed_once_then_served_from_cache(add_tests):
    add_tests(*VIT_CHENNAI, 5)
    calls = []

    def compute():
        calls.append(1)
        return stats.summarize(stats.rows_for_region(get_region("IN-TN")), "state")

    first = stats_cache.summary("state", "IN-TN", compute)
    second = stats_cache.summary("state", "IN-TN", compute)
    assert len(calls) == 1
    assert first == second
    assert first["sample_count"] == 5


def test_children_summaries_cache_all_36_states(add_tests):
    add_tests(*VIT_CHENNAI, 5)
    states = stats_cache.children_summaries(get_region("IN"))
    assert len(states) == 36
    assert _count() == 36
    tn = next(s for s in states if s["code"] == "IN-TN")
    assert tn["summary"]["sample_count"] == 5


def test_new_measurement_invalidates_its_areas(client, add_tests, asn_db):
    add_tests(*VIT_CHENNAI, 5)
    before = client.get("/api/map/states").get_json()["data"]
    assert next(s for s in before if s["code"] == "IN-TN")["summary"]["sample_count"] == 5

    payload = {"cell_id": "tf2cpct", "download_mbps": 30, "upload_mbps": 10, "latency_ms": 40,
               "jitter_ms": 5, "engine": "mlab-ndt7"}
    assert client.post("/api/measurements", json=payload, environ_base={"REMOTE_ADDR": JIO_IP}).status_code == 201

    after = client.get("/api/map/states").get_json()["data"]
    assert next(s for s in after if s["code"] == "IN-TN")["summary"]["sample_count"] == 6


def test_expired_entries_are_recomputed(add_tests, app):
    add_tests(*VIT_CHENNAI, 5)
    calls = []

    def compute():
        calls.append(1)
        return stats.summarize([], "state")

    stats_cache.summary("state", "IN-TN", compute)
    row = db.session.scalar(select(AreaStatistic))
    row.computed_at -= timedelta(minutes=app.config["STATS_CACHE_TTL_MINUTES"] + 1)
    db.session.commit()
    stats_cache.summary("state", "IN-TN", compute)
    assert len(calls) == 2
    assert _count() == 1  # the stale row was replaced, not duplicated


def test_cache_holds_no_demo_fields(add_tests):
    add_tests(*VIT_CHENNAI, 5)
    region = get_region("IN-TN")
    summary = stats_cache.region_summary(region, lambda: stats.rows_for_region(region))
    assert "includes_demo" not in summary
    assert not {"scope", "includes_demo"} & {c.name for c in AreaStatistic.__table__.columns}


def test_cached_summary_matches_fresh_calculation(add_tests):
    add_tests(*VIT_CHENNAI, 40, spread_cells=8)
    region = get_region("IN-TN")
    fresh = stats.summarize(stats.rows_for_region(region), "state")
    stats_cache.region_summary(region, lambda: stats.rows_for_region(region))
    cached = stats_cache.region_summary(region, lambda: [])  # must come from the cache now
    assert cached == fresh


def test_concurrent_cache_fill_is_harmless(add_tests, monkeypatch):
    """Two requests filling the same cache rows at once must not cause an error (seen on the home page)."""
    add_tests(*VIT_CHENNAI, 5)
    region = get_region("IN-TN")
    compute = lambda: stats.summarize(stats.rows_for_region(region), "state")  # noqa: E731
    first = stats_cache.summary("state", "IN-TN", compute)

    # Simulate the other request's row being committed between our cache check and our insert.
    monkeypatch.setattr(stats_cache, "_fresh_rows", lambda level, codes: {})
    second = stats_cache.summary("state", "IN-TN", compute)
    assert second == first
    assert _count() == 1
