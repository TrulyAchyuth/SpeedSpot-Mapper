"""Shared pytest fixtures: a fresh app + in-memory database for every test."""
from datetime import timedelta

import pytest

from backend import create_app
from backend.extensions import db
from backend.models import Measurement, Provider
from backend.services import grid, nqi
from backend.services.regions import seed_providers, seed_reference_regions
from backend.utils import geohash
from backend.utils.clock import hour_now

# Well-known points used across tests.
VIT_CHENNAI = (12.8406, 80.1534)
CHENNAI_CENTRAL = (13.0827, 80.2707)
DELHI = (28.6139, 77.2090)

# Production config for tests: a throwaway database is fine here.
PROD_OVERRIDES = {"SECRET_KEY": "x" * 64, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                  "ALLOW_SQLITE_IN_PRODUCTION": True}

# Public IPs used with the fake ASN database below.
JIO_IP = "49.36.0.1"            # really in AS55836 (Reliance Jio) in DB-IP
CLOUD_IP = "1.1.1.1"            # Cloudflare (AS13335) → VPN / cloud
OTHER_ISP_IP = "45.112.0.1"     # mapped below to an ISP that isn't in our provider list
UNLISTED_IP = "5.6.7.8"         # not in the fake database at all


class FakeAsnDatabase:
    """Stands in for the DB-IP file so tests control lookups exactly."""
    available = True

    def __init__(self, table: dict):
        self.table = table
        self.lookups = []

    def lookup(self, ip: str):
        self.lookups.append(ip)
        return self.table.get(ip)


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def seeded(app):
    seed_reference_regions()
    seed_providers()
    return app


@pytest.fixture
def asn_db(app):
    fake = FakeAsnDatabase({
        JIO_IP: (55836, "Reliance Jio Infocomm Limited"),
        CLOUD_IP: (13335, "Cloudflare, Inc."),
        OTHER_ISP_IP: (147000, "Example Broadband Pvt Ltd"),
    })
    app.extensions["asn_database"] = fake
    return fake


@pytest.fixture
def add_tests(seeded):
    """add_tests(lat, lng, count, download=..., provider="jio", spread_cells=1)

    TEST FIXTURE ONLY: inserts measurements into the temporary in-memory test database
    (bypassing the API) so tests control the data exactly. Never used by the application.
    `spread_cells` > 1 places tests in that many different neighbourhoods, stepping west (inland).
    """
    providers = {p.slug: p for p in db.session.query(Provider)}

    def _add(lat, lng, count, *, download=40.0, upload=15.0, latency=40.0, jitter=5.0,
             provider="jio", spread_cells=1, age_days=1, flagged=False):
        rows = []
        for i in range(count):
            # ~0.012° apart → a different geohash-6 neighbourhood for each step
            block = grid.ensure_block(geohash.encode(lat, lng - 0.012 * (i % spread_cells)))
            p = providers[provider] if provider else None
            rows.append(Measurement(
                created_at=hour_now() - timedelta(days=age_days), cell_id=block.cell_id,
                cell_lat=block.center_lat, cell_lng=block.center_lng, state_code=block.state_code,
                district_code=block.district_code, city_code=block.city_code,
                download_mbps=download, upload_mbps=upload, latency_ms=latency, jitter_ms=jitter,
                nqi=nqi.calculate(download, upload, latency, jitter),
                provider_id=p.id if p else None, provider_status="identified" if p else "unknown",
                asn=p.asns[0].asn if p else None, connection_type="unknown", engine="mlab-ndt7",
                source="user", flagged=flagged, flag_reason="implausible" if flagged else None,
            ))
        db.session.add_all(rows)
        db.session.commit()
        return rows

    return _add
