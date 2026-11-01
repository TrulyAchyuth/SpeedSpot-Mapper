"""Genuine data only: no generator, no demo rows, no demo labels — enforced down to the database."""
import importlib.util

import pytest
from flask_migrate import downgrade, upgrade
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend import create_app
from backend.extensions import db
from backend.services.regions import seed_providers, seed_reference_regions
from backend.utils import geohash
from tests.conftest import VIT_CHENNAI


def test_demo_generator_is_gone():
    assert importlib.util.find_spec("backend.services.demo_data") is None


def test_database_rejects_non_genuine_rows(add_tests):
    row = add_tests(*VIT_CHENNAI, 1)[0]
    with pytest.raises(IntegrityError):
        db.session.execute(text("UPDATE measurements SET source = 'demo' WHERE id = :id"), {"id": row.id})
        db.session.commit()
    db.session.rollback()


def test_api_responses_carry_no_demo_fields(client, add_tests):
    add_tests(*VIT_CHENNAI, 6)
    cell = geohash.encode(*VIT_CHENNAI, 6)
    for path in ["/api/regions/IN-TN/stats", "/api/map/states", f"/api/cells/{cell}/stats", "/api/insights?area=IN-TN",
                 "/api/statistics", "/api/measurements", f"/api/navigation/nearby?cell={geohash.encode(*VIT_CHENNAI)}",
                 "/api/cells?bbox=12.7,80.0,13.0,80.3&precision=6", "/api/export/areas.csv?area=IN-TN"]:
        body = client.get(path).get_data(as_text=True)
        assert "demo" not in body.lower(), path


def test_empty_database_gives_honest_empty_answers(client, seeded):
    """With no genuine measurements, nothing is invented: zero counts, no scores, no rankings."""
    india = client.get("/api/statistics").get_json()["data"]
    assert india["summary"]["sample_count"] == 0 and india["summary"]["status"] == "no_data"
    assert india["summary"]["score"] is None and india["summary"]["last_updated"] is None
    assert client.get("/api/providers/rankings").get_json()["data"]["providers"]["ranked"] == []
    assert all(s["summary"]["status"] == "no_data" for s in client.get("/api/map/states").get_json()["data"])
    assert client.get("/api/measurements").get_json()["data"] == []
    nearby = client.get(f"/api/navigation/nearby?cell={geohash.encode(*VIT_CHENNAI)}").get_json()["data"]
    assert nearby["destinations"] == [] and nearby["origin"]["current_score"] is None
    insights = client.get("/api/insights?area=IN").get_json()["data"]
    assert insights["trend"]["enough_data"] is False and insights["weakest"] == [] and insights["strongest"] == []


GENUINE_BLOCK, GENERATED_BLOCK = "tf2cpct", "tf34e2k"   # different neighbourhoods (tf2cpc vs tf34e2)


def _seed_old_schema_with_mixed_rows():
    """A database at the pre-cleanup revision holding genuine + generated rows, their cells and cache."""
    seed_reference_regions()
    seed_providers()
    for cell, precision in ((GENUINE_BLOCK, 7), (GENUINE_BLOCK[:6], 6), (GENERATED_BLOCK, 7), (GENERATED_BLOCK[:6], 6)):
        db.session.execute(text(
            "INSERT INTO grid_cells (cell_id, precision, center_lat, center_lng, min_lat, min_lng, max_lat, max_lng, "
            "first_seen_at) VALUES (:c, :p, 12.84, 80.15, 12.83, 80.14, 12.85, 80.16, '2026-11-01')"), {"c": cell, "p": precision})
    rows = [(GENUINE_BLOCK, "user", "mlab-ndt7"), (GENUINE_BLOCK, "user", "mlab-ndt7"),
            (GENERATED_BLOCK, "demo", "demo-generator"), (GENERATED_BLOCK, "demo", "demo-generator"),
            (GENUINE_BLOCK, "demo", "demo-generator")]   # a generated row inside a genuine block
    for cell, source, engine in rows:
        db.session.execute(text(
            "INSERT INTO measurements (created_at, cell_id, cell_lat, cell_lng, download_mbps, upload_mbps, "
            "latency_ms, jitter_ms, nqi, provider_status, connection_type, engine, source, flagged) VALUES "
            "('2026-11-01', :c, 12.84, 80.15, 10, 5, 40, 5, 50, 'unknown', 'unknown', :e, :s, false)"),
            {"c": cell, "s": source, "e": engine})
    db.session.execute(text(
        "INSERT INTO area_statistics (area_level, area_code, scope, status, sample_count, neighbourhood_count, "
        "block_count, district_count, includes_demo, computed_at) VALUES "
        "('state', 'IN-TN', 'with_demo', 'insufficient', 5, 2, 2, 1, true, '2026-11-01')"))
    db.session.commit()


def assert_genuine_only_after_upgrade():
    measurements = db.session.execute(text("SELECT cell_id, source FROM measurements ORDER BY id")).all()
    assert measurements == [(GENUINE_BLOCK, "user"), (GENUINE_BLOCK, "user")]   # genuine rows untouched
    cells = set(db.session.execute(text("SELECT cell_id FROM grid_cells")).scalars())
    assert cells == {GENUINE_BLOCK, GENUINE_BLOCK[:6]}                           # generated-only cells gone
    assert db.session.execute(text("SELECT count(*) FROM area_statistics")).scalar() == 0
    columns = {c["name"] for c in db.inspect(db.engine).get_columns("area_statistics")}
    assert not {"scope", "includes_demo"} & columns
    db.session.commit()  # end the read transaction so the next migration can lock the tables (PostgreSQL)


def test_migration_on_existing_sqlite_database(tmp_path):
    app = create_app("testing", {"SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'old.db'}"})
    with app.app_context():
        upgrade(revision="497721c7dce1")           # the schema as it was when demo rows were allowed
        _seed_old_schema_with_mixed_rows()
        upgrade()
        assert_genuine_only_after_upgrade()
        with pytest.raises(IntegrityError):         # and generated rows can't come back
            db.session.execute(text("UPDATE measurements SET source = 'demo'"))
            db.session.commit()
        db.session.rollback()

        downgrade(revision="497721c7dce1")         # rollback restores the old schema, keeps genuine rows
        assert db.session.execute(text("SELECT count(*) FROM measurements WHERE source = 'user'")).scalar() == 2
        assert "scope" in {c["name"] for c in db.inspect(db.engine).get_columns("area_statistics")}
        db.session.commit()
        upgrade()                                   # and can be re-applied cleanly
        assert_genuine_only_after_upgrade()
