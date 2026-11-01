"""Submitting and listing speed tests: validation, scoring, persistence, privacy, providers, limits."""
import math

import pytest
from sqlalchemy import inspect, select

from backend import create_app
from backend.extensions import db
from backend.models import GridCell, Measurement
from backend.services.regions import seed_providers, seed_reference_regions
from backend.utils import geohash
from tests.conftest import CLOUD_IP, JIO_IP, OTHER_ISP_IP, PROD_OVERRIDES, VIT_CHENNAI, FakeAsnDatabase

VALID = {
    "cell_id": geohash.encode(*VIT_CHENNAI),
    "download_mbps": 38, "upload_mbps": 12, "latency_ms": 45, "jitter_ms": 8,
    "connection_type": "wifi", "engine": "mlab-ndt7",
}


def post(client, payload=None, ip=JIO_IP, path="/api/measurements"):
    return client.post(path, json=VALID if payload is None else payload, environ_base={"REMOTE_ADDR": ip})


# ---------- Scoring and persistence ----------

def test_valid_submission_is_scored_on_the_server_and_persisted(client, seeded, asn_db):
    response = post(client, {**VALID, "nqi": 100, "score": 100})
    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["score"] == 74 and data["nqi"] == 74.4  # slide 7 worked example; client scores ignored
    assert data["band"] == "good"
    assert data["state_code"] == "IN-TN" and data["district_code"].startswith("IN-TN-D")
    assert data["counted"] is True and data["message"] is None
    assert data["provider"]["provider"]["name"] == "Jio"

    stored = db.session.scalar(select(Measurement))
    assert (stored.download_mbps, stored.upload_mbps, stored.latency_ms, stored.jitter_ms) == (38, 12, 45, 8)
    assert stored.nqi == 74.4 and stored.source == "user" and stored.connection_type == "wifi"
    assert stored.provider.slug == "jio" and stored.provider_status == "identified" and stored.asn == 55836
    assert stored.created_at.minute == 0 and stored.created_at.second == 0  # rounded to the hour


def test_grid_cells_are_created_for_block_and_neighbourhood(client, seeded, asn_db):
    post(client)
    cells = {c.cell_id: c for c in db.session.scalars(select(GridCell))}
    assert set(cells) == {VALID["cell_id"], VALID["cell_id"][:6]}
    block = cells[VALID["cell_id"]]
    assert block.precision == 7 and block.state_code == "IN-TN"
    assert block.min_lat < block.center_lat < block.max_lat
    post(client)  # a second test in the same block doesn't duplicate cells
    assert db.session.query(GridCell).count() == 2


# ---------- Privacy ----------

def test_nothing_identifying_is_stored(client, seeded, asn_db):
    post(client, ip="49.36.0.1")
    columns = {c["name"] for c in inspect(db.engine).get_columns("measurements")}
    for forbidden in ("ip", "ip_address", "client_ip", "lat", "lng", "latitude", "longitude",
                      "device_id", "user_agent", "accuracy"):
        assert forbidden not in columns
    for table in inspect(db.engine).get_table_names():
        for row in db.session.execute(db.text(f"SELECT * FROM {table}")):
            assert "49.36.0.1" not in str(tuple(row)), f"IP found in table {table}"
    row = db.session.execute(select(Measurement.__table__)).mappings().one()
    south, west, north, east = geohash.bounds(VALID["cell_id"])
    assert row["cell_lat"] == pytest.approx((south + north) / 2, abs=1e-5)  # block centre only


def test_exact_coordinates_are_rejected(client, seeded, asn_db):
    response = post(client, {**VALID, "cell_id": None, "lat": 12.840612, "lng": 80.153421})
    assert response.status_code == 400
    assert "cell_id" in response.get_json()["error"]["details"]


# ---------- Provider handling ----------

def test_vpn_results_are_stored_but_not_counted(client, seeded, asn_db):
    data = post(client, ip=CLOUD_IP).get_json()["data"]
    assert data["counted"] is False
    assert "VPN" in data["message"]
    assert data["provider"]["status"] == "vpn_or_hosting"
    stored = db.session.scalar(select(Measurement))
    assert stored.flagged and stored.flag_reason == "vpn_or_hosting" and stored.provider_id is None
    assert client.get("/api/regions/IN-TN/stats").get_json()["data"]["summary"]["sample_count"] == 0


def test_unlisted_isp_is_kept_with_its_network_name(client, seeded, asn_db):
    data = post(client, ip=OTHER_ISP_IP).get_json()["data"]
    assert data["counted"] is True
    assert data["provider"]["status"] == "other_isp" and data["provider"]["network"] == "Example Broadband Pvt Ltd"
    stored = db.session.scalar(select(Measurement))
    assert stored.provider_id is None and stored.asn == 147000 and stored.asn_org == "Example Broadband Pvt Ltd"


def test_unknown_provider_is_honest(client, seeded, asn_db):
    data = post(client, ip="127.0.0.1").get_json()["data"]
    assert data["provider"]["status"] == "unknown" and data["provider"]["provider"] is None
    assert data["counted"] is True


def test_dev_client_ip_override_is_ignored_in_production(seeded):
    app = create_app("production", {**PROD_OVERRIDES, "DEV_CLIENT_IP": JIO_IP})
    with app.test_request_context(environ_base={"REMOTE_ADDR": "127.0.0.1"}):
        from backend.utils.client_ip import client_ip
        assert client_ip() == "127.0.0.1"


# ---------- Validation ----------

@pytest.mark.parametrize("field,value", [
    ("cell_id", "tf2cp"), ("cell_id", "INVALID"), ("cell_id", 12345),
    ("download_mbps", -1), ("download_mbps", 0), ("download_mbps", "fast"), ("download_mbps", None),
    ("upload_mbps", 0), ("upload_mbps", 999_999), ("latency_ms", 0), ("latency_ms", None),
    ("jitter_ms", -0.1), ("jitter_ms", True), ("engine", "made-up"), ("engine", None),
    ("connection_type", "pigeon"),
])
def test_invalid_fields_are_rejected(client, seeded, asn_db, field, value):
    response = post(client, {**VALID, field: value})
    assert response.status_code == 400
    error = response.get_json()["error"]
    assert error["code"] == "validation_error"
    assert field in error["details"]
    assert db.session.scalar(select(Measurement)) is None


def test_zero_jitter_is_valid(client, seeded, asn_db):
    assert post(client, {**VALID, "jitter_ms": 0}).status_code == 201


def test_missing_fields_are_all_reported_at_once(client, seeded, asn_db):
    details = post(client, {"engine": "mlab-ndt7"}).get_json()["error"]["details"]
    assert {"cell_id", "download_mbps", "upload_mbps", "latency_ms", "jitter_ms"} <= set(details)


def test_nan_is_rejected():
    from backend.services.measurements import validate
    from backend.utils.responses import ApiError
    with pytest.raises(ApiError):
        validate({**VALID, "download_mbps": math.nan})


@pytest.mark.parametrize("body,content_type", [("hello", "text/plain"), ("[1, 2]", "application/json"), ("{bad json", "application/json")])
def test_non_object_bodies_are_rejected(client, seeded, asn_db, body, content_type):
    assert client.post("/api/measurements", data=body, content_type=content_type).status_code == 400


def test_tests_outside_india_are_rejected(client, seeded, asn_db):
    response = post(client, {**VALID, "cell_id": geohash.encode(51.5, -0.12)})
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "outside_service_area"
    assert db.session.query(GridCell).count() == 0


@pytest.mark.parametrize("field,value", [("download_mbps", 5000), ("upload_mbps", 4000), ("latency_ms", 0.5)])
def test_implausible_results_are_kept_out_of_scores(client, seeded, asn_db, field, value):
    data = post(client, {**VALID, field: value}).get_json()["data"]
    assert data["counted"] is False and "unusual" in data["message"]


# ---------- Rate limiting ----------

def test_rate_limit_is_shared_across_api_paths():
    app = create_app("testing", {"RATELIMIT_ENABLED": True, "MEASUREMENT_RATE_LIMIT": "3 per hour"})
    with app.app_context():
        db.create_all()
        seed_reference_regions()
        seed_providers()
        app.extensions["asn_database"] = FakeAsnDatabase({})
        client = app.test_client()
        codes = [post(client, path=p).status_code for p in
                 ("/api/measurements", "/api/v1/measurements", "/api/measurements", "/api/v1/measurements")]
        assert codes == [201, 201, 201, 429]
        assert post(client).get_json()["error"]["code"] == "rate_limited"
        db.drop_all()


# ---------- Listing ----------

def test_list_shows_counted_tests_newest_first(client, add_tests):
    add_tests(*VIT_CHENNAI, 3, download=20)
    add_tests(*VIT_CHENNAI, 2, download=90, flagged=True)  # not counted → not listed
    body = client.get("/api/measurements").get_json()
    assert body["meta"]["count"] == 3
    ids = [m["id"] for m in body["data"]]
    assert ids == sorted(ids, reverse=True)
    item = body["data"][0]
    assert set(item) >= {"tested_at", "download_mbps", "upload_mbps", "latency_ms", "jitter_ms", "score",
                         "band", "provider", "neighbourhood", "district_code"}
    assert "is_demo" not in item
    assert "cell_id" not in item  # never the ~150 m block in public lists


def test_list_hides_neighbourhood_until_five_tests(client, add_tests):
    add_tests(*VIT_CHENNAI, 4)
    assert all(m["neighbourhood"] is None for m in client.get("/api/measurements").get_json()["data"])
    add_tests(*VIT_CHENNAI, 1)
    assert all(m["neighbourhood"] == geohash.encode(*VIT_CHENNAI, 6)
               for m in client.get("/api/measurements").get_json()["data"])


def test_list_pagination_and_filters(client, add_tests):
    add_tests(*VIT_CHENNAI, 5, provider="airtel")
    add_tests(*VIT_CHENNAI, 3, provider="jio")
    page1 = client.get("/api/measurements?limit=4").get_json()
    assert page1["meta"]["count"] == 4 and page1["meta"]["next_before"]
    page2 = client.get(f"/api/measurements?limit=4&before={page1['meta']['next_before']}").get_json()
    assert page2["meta"]["count"] == 4 and page2["meta"]["next_before"] is None
    assert not {m["id"] for m in page1["data"]} & {m["id"] for m in page2["data"]}
    airtel = client.get("/api/measurements?provider=airtel").get_json()["data"]
    assert len(airtel) == 5 and all(m["provider"]["slug"] == "airtel" for m in airtel)
    assert client.get("/api/measurements?area=IN-DL").get_json()["data"] == []
    assert len(client.get("/api/measurements?area=IN-TN").get_json()["data"]) == 8


@pytest.mark.parametrize("query,status", [
    ("limit=0", 400), ("limit=101", 400), ("limit=abc", 400), ("before=-5", 400),
    ("provider=nobody", 404), ("area=IN-XX", 404), ("area=zzzz", 400),
])
def test_list_validates_parameters(client, seeded, query, status):
    assert client.get(f"/api/measurements?{query}").status_code == status
