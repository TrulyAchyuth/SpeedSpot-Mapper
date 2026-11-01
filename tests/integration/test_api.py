import pytest


from backend.utils import geohash
from tests.conftest import VIT_CHENNAI


def test_health_reports_ok(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.get_json() == {"data": {"status": "ok", "database": "ok"}}


def test_unknown_api_route_returns_json_error_envelope(client):
    response = client.get("/api/v1/nope")
    assert response.status_code == 404
    assert response.mimetype == "application/json"
    body = response.get_json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"]


def test_wrong_method_returns_json_405(client):
    response = client.post("/api/v1/health")
    assert response.status_code == 405
    assert response.get_json()["error"]["code"] == "method_not_allowed"


# ---------- Regions and search ----------

def test_list_states_of_india(client, seeded):
    body = client.get("/api/v1/regions?level=state&parent=IN").get_json()
    assert body["meta"]["count"] == 36
    names = [r["name"] for r in body["data"]]
    assert names == sorted(names)
    assert {"code": "IN-TN", "name": "Tamil Nadu", "level": "state", "kind": "state"} in body["data"]


def test_region_detail_includes_breadcrumb_bbox_and_districts(client, seeded):
    body = client.get("/api/v1/regions/in-tn").get_json()["data"]  # codes are case-insensitive
    assert body["code"] == "IN-TN"
    assert [r["code"] for r in body["breadcrumb"]] == ["IN", "IN-TN"]
    assert len(body["bbox"]) == 4
    assert len(body["children"]) >= 38  # Tamil Nadu's districts
    assert all(c["level"] == "district" for c in body["children"])


def test_invalid_level_is_a_validation_error(client, seeded):
    response = client.get("/api/v1/regions?level=planet")
    assert response.status_code == 400
    error = response.get_json()["error"]
    assert error["code"] == "invalid_parameter"
    assert "level" in error["details"]


def test_unknown_region_is_404(client, seeded):
    assert client.get("/api/v1/regions/IN-XX").status_code == 404
    assert client.get("/api/v1/regions?parent=IN-XX").status_code == 404


def test_search_finds_states_districts_and_cities(client, seeded):
    results = client.get("/api/v1/search?q=chenn").get_json()["data"]
    levels = {r["level"] for r in results}
    assert {"district", "city"} <= levels
    assert all("chenn" in r["name"].lower() for r in results)
    assert results[0]["bbox"] and results[0]["label"]


def test_search_ignores_short_queries_and_wildcards(client, seeded):
    assert client.get("/api/v1/search?q=c").get_json()["data"] == []
    assert client.get("/api/v1/search?q=%25%25").get_json()["data"] == []


def test_locate_takes_only_a_block_code(client, seeded):
    cell = geohash.encode(*VIT_CHENNAI)
    data = client.get(f"/api/v1/locate?cell={cell}").get_json()["data"]
    assert data["places"][0]["code"] == "IN-TN"
    assert data["places"][1]["level"] == "district"
    assert client.get("/api/v1/locate?lat=12.8&lng=80.1").status_code == 400


# ---------- Statistics ----------

def test_region_stats_with_no_data(client, seeded):
    data = client.get("/api/v1/regions/IN/stats").get_json()["data"]
    assert data["summary"]["status"] == "no_data"
    assert data["summary"]["score"] is None
    assert len(data["children"]) == 36
    assert all(c["summary"]["status"] == "no_data" for c in data["children"])


def test_region_stats_with_data(client, add_tests):
    add_tests(*VIT_CHENNAI, 40, spread_cells=8)
    data = client.get("/api/v1/regions/IN-TN/stats").get_json()["data"]
    assert data["summary"]["sample_count"] == 40
    assert data["summary"]["status"] == "insufficient"  # one district only
    district = next(c for c in data["children"] if c["summary"]["sample_count"])
    assert district["summary"]["status"] == "ok"        # 40 tests, 8 neighbourhoods
    assert district["summary"]["band"] in {"good", "fair", "weak"}


def test_cells_in_bbox(client, add_tests):
    add_tests(*VIT_CHENNAI, 6)
    add_tests(13.0827, 80.2707, 2)
    cells = client.get("/api/v1/cells?bbox=12.7,80.0,13.2,80.4&precision=6").get_json()["data"]
    statuses = sorted(c["status"] for c in cells)
    assert statuses == ["insufficient", "ok"]
    ok = next(c for c in cells if c["status"] == "ok")
    assert ok["sample_count"] == 6 and len(ok["bounds"]) == 4 and ok["last_updated"].endswith("Z")


def test_cells_reject_bad_or_huge_areas(client, seeded):
    assert client.get("/api/v1/cells?bbox=nonsense&precision=6").status_code == 400
    assert client.get("/api/v1/cells?bbox=10,70,30,90&precision=6").get_json()["error"]["code"] == "area_too_large"
    assert client.get("/api/v1/cells?bbox=12,80,12.1,80.1&precision=9").status_code == 400


def test_cell_stats_and_area_description(client, add_tests):
    add_tests(*VIT_CHENNAI, 5)
    cell = geohash.encode(*VIT_CHENNAI, 6)
    data = client.get(f"/api/v1/cells/{cell}/stats").get_json()["data"]
    assert data["summary"]["status"] == "ok"
    assert data["area"]["level"] == "neighbourhood"
    assert data["area"]["name"].startswith("Neighbourhood near")
    assert data["area"]["breadcrumb"][1]["code"] == "IN-TN"


def test_provider_rankings_and_insights_endpoints(client, add_tests):
    add_tests(*VIT_CHENNAI, 12, provider="airtel", spread_cells=3)
    rankings = client.get("/api/v1/providers/rankings?area=IN-TN").get_json()["data"]
    assert rankings["providers"]["ranked"][0]["name"] == "Airtel"

    insights = client.get("/api/v1/insights?area=IN-TN").get_json()["data"]
    assert insights["summary"]["sample_count"] == 12
    assert set(insights["neighbourhood_distribution"]) == {"good", "fair", "weak", "insufficient"}
    assert all("name" in n for n in insights["strongest"])


def test_area_parameter_is_validated(client, seeded):
    assert client.get("/api/v1/insights").status_code == 400
    assert client.get("/api/v1/insights?area=IN-XX").status_code == 404
    assert client.get("/api/v1/providers/rankings?area=zzzz").status_code == 400


# ---------- /api alias and milestone endpoints ----------

@pytest.mark.parametrize("path", ["/api/health", "/api/v1/health"])
def test_api_is_available_at_both_prefixes(client, path):
    assert client.get(path).get_json()["data"]["status"] == "ok"


def test_map_states_returns_all_36_with_summaries(client, add_tests):
    add_tests(*VIT_CHENNAI, 5)
    states = client.get("/api/map/states").get_json()["data"]
    assert len(states) == 36
    tn = next(s for s in states if s["code"] == "IN-TN")
    assert tn["summary"]["sample_count"] == 5 and tn["summary"]["status"] == "insufficient"
    assert len(tn["bbox"]) == 4


def test_map_districts(client, add_tests):
    add_tests(*VIT_CHENNAI, 40, spread_cells=8)
    body = client.get("/api/map/districts?state=in-tn").get_json()
    assert body["meta"]["state"] == "IN-TN" and body["meta"]["count"] >= 38
    scored = [d for d in body["data"] if d["summary"]["status"] == "ok"]
    assert len(scored) == 1


@pytest.mark.parametrize("query,status", [("", 400), ("?state=IN-XX", 404), ("?state=IN", 400), ("?state=IN-TN-D568", 400)])
def test_map_districts_validation(client, seeded, query, status):
    assert client.get(f"/api/map/districts{query}").status_code == status


def test_map_cells_alias(client, add_tests):
    add_tests(*VIT_CHENNAI, 5)
    a = client.get("/api/map/cells?bbox=12.7,80.0,13.0,80.3&precision=7").get_json()["data"]
    b = client.get("/api/cells?bbox=12.7,80.0,13.0,80.3&precision=7").get_json()["data"]
    assert a == b and a[0]["level"] == "block" and a[0]["status"] == "ok"


def test_providers_list(client, add_tests):
    add_tests(*VIT_CHENNAI, 4, provider="act")
    items = client.get("/api/providers").get_json()["data"]
    assert len(items) == 18
    act = next(p for p in items if p["slug"] == "act")
    assert act["sample_count"] == 4 and act["asn_count"] == 4 and act["kind"] == "broadband"


def test_statistics_defaults_to_india(client, add_tests):
    add_tests(*VIT_CHENNAI, 6, provider="jio")
    add_tests(28.6139, 77.2090, 2, provider=None)
    data = client.get("/api/statistics").get_json()["data"]
    assert data["area"]["code"] == "IN"
    assert data["summary"]["sample_count"] == 8
    assert data["coverage"]["states_tested"] == 2 and data["coverage"]["neighbourhoods_with_score"] == 1
    assert data["providers"]["identified_share"] == 0.75
    assert data["children_with_score"] == {"level": "state", "count": 0, "total": 36}
    assert data["freshness_window_days"] == 180


def test_statistics_for_a_cell(client, add_tests):
    add_tests(*VIT_CHENNAI, 5)
    data = client.get(f"/api/statistics?area={geohash.encode(*VIT_CHENNAI, 6)}").get_json()["data"]
    assert data["summary"]["status"] == "ok" and "children_with_score" not in data


def test_rankings_default_to_india(client, add_tests):
    add_tests(*VIT_CHENNAI, 10, provider="airtel")
    data = client.get("/api/providers/rankings").get_json()["data"]
    assert data["area"]["code"] == "IN" and data["providers"]["ranked"][0]["slug"] == "airtel"


def test_me_provider(client, seeded, asn_db):
    data = client.get("/api/me/provider", environ_base={"REMOTE_ADDR": "49.36.0.1"}).get_json()["data"]
    assert data["status"] == "identified" and data["provider"]["name"] == "Jio"
    assert data["lookup_available"] is True
    local = client.get("/api/me/provider").get_json()["data"]  # test client = 127.0.0.1
    assert local["status"] == "unknown" and local["provider"] is None
