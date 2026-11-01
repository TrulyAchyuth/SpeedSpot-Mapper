"""Duplicate submissions and database-level integrity."""
from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from backend.extensions import db
from backend.models import Measurement
from backend.utils import geohash
from tests.conftest import JIO_IP, VIT_CHENNAI

VALID = {"cell_id": geohash.encode(*VIT_CHENNAI), "download_mbps": 38, "upload_mbps": 12, "latency_ms": 45,
         "jitter_ms": 8, "engine": "mlab-ndt7", "submission_id": "6f1c2a3e-8b4d-4c2a-9e6f-1a2b3c4d5e6f"}


def post(client, payload):
    return client.post("/api/measurements", json=payload, environ_base={"REMOTE_ADDR": JIO_IP})


def test_duplicate_submission_is_rejected(client, seeded, asn_db):
    assert post(client, VALID).status_code == 201
    second = post(client, VALID)
    assert second.status_code == 409
    assert second.get_json()["error"]["code"] == "duplicate_submission"
    assert db.session.query(Measurement).count() == 1


def test_different_submissions_are_both_kept(client, seeded, asn_db):
    post(client, VALID)
    post(client, {**VALID, "submission_id": "0a1b2c3d-4e5f-4a7b-8c9d-0e1f2a3b4c5d"})
    post(client, {k: v for k, v in VALID.items() if k != "submission_id"})  # optional
    assert db.session.query(Measurement).count() == 3


@pytest.mark.parametrize("value", ["not-a-uuid", "6F1C2A3E-8B4D-4C2A-9E6F-1A2B3C4D5E6F",
                                   "6f1c2a3e-8b4d-1c2a-9e6f-1a2b3c4d5e6f", 12345])
def test_submission_id_must_be_a_random_uuid(client, seeded, asn_db, value):
    response = post(client, {**VALID, "submission_id": value})
    assert response.status_code == 400 and "submission_id" in response.get_json()["error"]["details"]


def _row(**overrides):
    values = dict(created_at=datetime(2026, 11, 1), cell_id=geohash.encode(*VIT_CHENNAI), cell_lat=12.84,
                  cell_lng=80.15, download_mbps=10, upload_mbps=5, latency_ms=40, jitter_ms=5, nqi=50,
                  provider_status="unknown", connection_type="unknown", engine="mlab-ndt7", source="user")
    values.update(overrides)
    return Measurement(**values)


@pytest.mark.parametrize("field,value", [
    ("download_mbps", -1), ("upload_mbps", 0), ("latency_ms", 0), ("jitter_ms", -0.5), ("nqi", 101),
    ("source", "made-up"), ("provider_status", "guessed"), ("connection_type", "pigeon"),
])
def test_database_refuses_impossible_values(client, seeded, asn_db, field, value):
    post(client, {k: v for k, v in VALID.items() if k != "submission_id"})  # creates the grid cell
    db.session.add(_row(**{field: value}))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_foreign_keys_are_enforced(seeded):
    db.session.add(_row(cell_id="tf2cpzz"))  # no such grid cell
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
