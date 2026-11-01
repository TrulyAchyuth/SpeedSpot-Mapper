import json
import re
from pathlib import Path

from sqlalchemy import func, select

from backend.extensions import db
from backend.models import Region
from backend.services import geo_lookup
from backend.services.regions import REFERENCE_DIR, load_reference, seed_reference_regions
from tests.conftest import DELHI, VIT_CHENNAI

GEO_DIR = Path(__file__).resolve().parents[2] / "frontend" / "static" / "geo"


def test_reference_file_has_28_states_and_8_union_territories():
    states = load_reference()["states"]
    kinds = [s["kind"] for s in states]
    assert kinds.count("state") == 28
    assert kinds.count("union_territory") == 8


def test_reference_codes_and_names_are_unique_and_well_formed():
    states = load_reference()["states"]
    codes = [s["code"] for s in states]
    assert len(set(codes)) == len(codes)
    assert len({s["name"] for s in states}) == len(states)
    assert len({s["lgd_code"] for s in states}) == 36
    assert all(re.fullmatch(r"IN-[A-Z]{2}", c) for c in codes)


def test_boundary_files_cover_every_state_and_district():
    states = json.loads((GEO_DIR / "states.geojson").read_text())["features"]
    assert {f["properties"]["code"] for f in states} == {s["code"] for s in load_reference()["states"]}
    index = load_reference(REFERENCE_DIR / "india_boundaries_index.json")
    assert len(index["districts"]) == 785
    district_files = {p.stem for p in (GEO_DIR / "districts").glob("*.geojson")}
    assert district_files == {s["code"] for s in load_reference()["states"]}


def test_seeding_builds_the_full_hierarchy(app):
    result = seed_reference_regions()
    counts = dict(db.session.execute(select(Region.level, func.count()).group_by(Region.level)).all())
    assert counts["country"] == 1 and counts["state"] == 36 and counts["district"] == 785
    assert counts["city"] > 1000
    assert result["total"] == sum(counts.values())

    chennai_city = db.session.scalar(select(Region).where(Region.level == "city", Region.name == "Chennai"))
    assert [r.level for r in chennai_city.breadcrumb()] == ["country", "state", "district", "city"]
    assert chennai_city.breadcrumb()[1].code == "IN-TN"
    assert chennai_city.label() == "City in Chennai, Tamil Nadu"


def test_seeding_is_idempotent(app):
    first = seed_reference_regions()
    second = seed_reference_regions()
    assert second["created"] == 0
    assert first["total"] == second["total"] == db.session.scalar(select(func.count(Region.id)))


def test_states_and_districts_have_map_bounds(app):
    seed_reference_regions()
    kerala = db.session.scalar(select(Region).where(Region.code == "IN-KL"))
    south, west, north, east = kerala.bbox()
    assert 8 < south < north < 13 and 74 < west < east < 78


def test_locate_points_in_districts():
    vit = geo_lookup.locate(*VIT_CHENNAI)
    assert vit.state_code == "IN-TN"
    assert vit.district_code.startswith("IN-TN-D")
    delhi = geo_lookup.locate(*DELHI)
    assert delhi.state_code == "IN-DL"


def test_locate_outside_india_is_none():
    assert geo_lookup.locate(10.0, 70.0) is None   # Arabian Sea
    assert geo_lookup.locate(51.5, -0.12) is None  # London
