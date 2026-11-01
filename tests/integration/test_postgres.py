"""The production database: real Alembic migrations and key queries on PostgreSQL.

Starts a throwaway PostgreSQL server with `pgserver` (dev dependency). Skipped if it
isn't installed. SQLite and PostgreSQL disagree on some SQL (e.g. GROUP BY rules),
so this catches bugs the in-memory SQLite tests can't.
"""
import pytest

pgserver = pytest.importorskip("pgserver")

from flask_migrate import downgrade, upgrade  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from backend import create_app  # noqa: E402
from backend.extensions import db  # noqa: E402
from backend.services.regions import seed_providers, seed_reference_regions  # noqa: E402
from tests.conftest import JIO_IP, FakeAsnDatabase  # noqa: E402


@pytest.fixture(scope="module")
def pg_app(tmp_path_factory):
    server = pgserver.get_server(str(tmp_path_factory.mktemp("pg")), cleanup_mode="stop")
    uri = server.get_uri().replace("postgresql://", "postgresql+psycopg://", 1)
    app = create_app("testing", {"SQLALCHEMY_DATABASE_URI": uri})
    app.extensions["asn_database"] = FakeAsnDatabase({JIO_IP: (55836, "Reliance Jio Infocomm Limited")})
    with app.app_context():
        upgrade()
        seed_reference_regions()
        seed_providers()
        yield app
        db.session.remove()
        db.engine.dispose()
    server.cleanup()


def test_runs_on_postgresql(pg_app):
    assert db.engine.dialect.name == "postgresql"


def test_submit_list_and_aggregate(pg_app):
    client = pg_app.test_client()
    for i in range(6):
        response = client.post("/api/measurements", environ_base={"REMOTE_ADDR": JIO_IP}, json={
            "cell_id": "tf2cpct", "download_mbps": 30 + i, "upload_mbps": 10, "latency_ms": 40, "jitter_ms": 5,
            "engine": "mlab-ndt7", "submission_id": f"00000000-0000-4000-8000-00000000000{i}"})
        assert response.status_code == 201, response.get_json()
    assert client.post("/api/measurements", environ_base={"REMOTE_ADDR": JIO_IP}, json={
        "cell_id": "tf2cpct", "download_mbps": 30, "upload_mbps": 10, "latency_ms": 40, "jitter_ms": 5,
        "engine": "mlab-ndt7", "submission_id": "00000000-0000-4000-8000-000000000000"}).status_code == 409

    listed = client.get("/api/measurements").get_json()
    assert listed["meta"]["count"] == 6 and listed["data"][0]["neighbourhood"] == "tf2cpc"
    for path in ["/api/map/states", "/api/map/districts?state=IN-TN", "/api/regions/IN-TN/stats?period=30",
                 "/api/cells?bbox=12.7,80.0,13.0,80.3&precision=7", "/api/search?q=chenn",
                 "/api/statistics", "/api/insights?area=IN-TN", "/api/providers/rankings?area=IN-TN",
                 "/api/navigation/nearby?cell=tf2cpct", "/api/export/areas.csv?area=IN-TN&type=neighbourhoods"]:
        assert client.get(path).status_code == 200, path
    cells = client.get("/api/cells?bbox=12.7,80.0,13.0,80.3&precision=7").get_json()["data"]
    assert cells[0]["status"] == "ok" and cells[0]["sample_count"] == 6


def test_check_constraints_are_enforced(pg_app):
    with pytest.raises(IntegrityError):
        db.session.execute(db.text("UPDATE measurements SET download_mbps = -5"))
        db.session.commit()
    db.session.rollback()


def test_genuine_data_migration_on_postgresql(tmp_path_factory):
    """The 'genuine data only' migration on a separate, older PostgreSQL database with mixed rows."""
    from sqlalchemy import text
    from tests.integration.test_data_integrity import _seed_old_schema_with_mixed_rows, assert_genuine_only_after_upgrade

    server = pgserver.get_server(str(tmp_path_factory.mktemp("pg-migration")), cleanup_mode="stop")
    app = create_app("testing", {"SQLALCHEMY_DATABASE_URI": server.get_uri().replace("postgresql://", "postgresql+psycopg://", 1)})
    with app.app_context():
        upgrade(revision="497721c7dce1")
        _seed_old_schema_with_mixed_rows()
        upgrade()
        assert_genuine_only_after_upgrade()
        downgrade(revision="497721c7dce1")
        assert db.session.execute(text("SELECT count(*) FROM measurements WHERE source = 'user'")).scalar() == 2
        db.session.commit()  # release locks before the next migration
        upgrade()
        assert_genuine_only_after_upgrade()
        db.session.remove()
        db.engine.dispose()
    server.cleanup()
