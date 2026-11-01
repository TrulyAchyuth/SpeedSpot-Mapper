import pytest

from backend.services import nqi
from backend.utils import geohash

# Shared with tests/js/geohash.test.mjs so Python and JS agree exactly.
GEOHASH_VECTORS = [
    (57.64911, 10.40744, 11, "u4pruydqqvj"),  # classic reference example
    (42.6, -5.6, 5, "ezs42"),                 # Wikipedia example
    (12.8406, 80.1534, 7, "tf2cpct"),         # VIT Chennai (cross-implementation check)
]


def test_slide_7_worked_example():
    # 38 Mbps down · 12 up · 45 ms · 8 ms jitter → D .76, U .60, L .775, J .84 → 74.4 → shown as 74
    parts = nqi.components(38, 12, 45, 8)
    assert parts == pytest.approx({"download": 0.76, "upload": 0.60, "latency": 0.775, "jitter": 0.84})
    assert nqi.calculate(38, 12, 45, 8) == 74.4
    assert nqi.band(round(74.4)) == "good"


def test_components_are_capped_and_floored():
    assert nqi.calculate(500, 200, 0, 0) == 100.0
    assert nqi.calculate(0, 0, 400, 100) == 0.0


@pytest.mark.parametrize("score,band", [(100, "good"), (70, "good"), (69, "fair"), (40, "fair"), (39, "weak"), (0, "weak"), (None, None)])
def test_bands(score, band):
    assert nqi.band(score) == band


@pytest.mark.parametrize("lat,lng,precision,expected", GEOHASH_VECTORS)
def test_geohash_encode(lat, lng, precision, expected):
    assert geohash.encode(lat, lng, precision) == expected


@pytest.mark.parametrize("lat,lng,precision,code", GEOHASH_VECTORS)
def test_geohash_bounds_contain_the_point(lat, lng, precision, code):
    south, west, north, east = geohash.bounds(code)
    assert south <= lat <= north and west <= lng <= east


def test_block_is_about_150_metres_in_chennai():
    south, west, north, east = geohash.bounds(geohash.encode(12.84, 80.15))
    height_m = (north - south) * 111_320
    width_m = (east - west) * 111_320 * 0.9744  # cos(12.84°)
    assert 150 < height_m < 156 and 145 < width_m < 152


def test_geohash_validation():
    assert geohash.is_valid("tf2cpct", 7)
    assert not geohash.is_valid("tf2cpc", 7)
    assert not geohash.is_valid("tf2cpqa")  # 'a' isn't in the geohash alphabet
    assert not geohash.is_valid("")
    assert not geohash.is_valid(None)
