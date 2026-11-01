"""Browser tests: the real app in a background thread, driven by Playwright (Chromium).

  pytest tests/e2e            (needs: playwright install chromium)

The app runs against a throwaway SQLite file with a small, known set of test measurements.
All requests to other hosts are intercepted: map tiles get a blank image, and nothing
reaches M-Lab or the routing service unless a test provides a stand-in response.
"""
import base64
import threading
from datetime import timedelta

import pytest
from werkzeug.serving import make_server

from backend import create_app
from backend.extensions import db
from backend.models import Measurement, Provider
from backend.services import grid, nqi
from backend.services.regions import seed_providers, seed_reference_regions
from backend.utils import geohash
from backend.utils.clock import hour_now
from tests.conftest import JIO_IP, FakeAsnDatabase

VIT = (12.8406, 80.1534)
BLANK_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")


def _seed_measurements():
    providers = {p.slug: p for p in db.session.query(Provider)}

    def add(lat, lng, count, download, upload, latency, jitter, provider="jio", days=2):
        block = grid.ensure_block(geohash.encode(lat, lng))
        for _ in range(count):
            p = providers[provider]
            db.session.add(Measurement(
                created_at=hour_now() - timedelta(days=days), cell_id=block.cell_id, cell_lat=block.center_lat,
                cell_lng=block.center_lng, state_code=block.state_code, district_code=block.district_code,
                city_code=block.city_code, download_mbps=download, upload_mbps=upload, latency_ms=latency,
                jitter_ms=jitter, nqi=nqi.calculate(download, upload, latency, jitter), provider_id=p.id,
                provider_status="identified", asn=p.asns[0].asn, connection_type="wifi", engine="mlab-ndt7",
                source="user"))

    add(*VIT, 5, 3, 1, 300, 60)                                   # weak block where "the user" is
    add(VIT[0] + 0.0045, VIT[1], 6, 90, 30, 20, 2)                # good block ~500 m north
    add(VIT[0] + 0.009, VIT[1], 5, 60, 20, 30, 4, "airtel")       # good block ~1 km north
    add(13.0827, 80.2707, 8, 25, 8, 60, 10, "airtel", days=40)    # central Chennai
    db.session.commit()


@pytest.fixture(scope="session")
def live_server(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("e2e") / "e2e.db"
    app = create_app("testing", {"SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file}", "DEV_CLIENT_IP": JIO_IP})
    app.extensions["asn_database"] = FakeAsnDatabase({JIO_IP: (55836, "Reliance Jio Infocomm Limited")})
    with app.app_context():
        db.create_all()
        seed_reference_regions()
        seed_providers()
        _seed_measurements()
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield {"url": f"http://127.0.0.1:{server.server_port}", "app": app}
    server.shutdown()


@pytest.fixture(scope="session")
def base_url(live_server):
    return live_server["url"]


@pytest.fixture
def offline(page, base_url):
    """Keep tests self-contained: block every host except the app itself."""
    def handle(route):
        url = route.request.url
        if url.startswith(base_url):
            return route.continue_()
        if "tile.openstreetmap.org" in url:
            return route.fulfill(status=200, content_type="image/png", body=BLANK_PNG)
        return route.abort()
    page.route("**/*", handle)
    return page


@pytest.fixture
def console_errors(page):
    errors = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    return errors
