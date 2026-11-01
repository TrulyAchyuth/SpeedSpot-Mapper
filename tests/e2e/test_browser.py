"""End-to-end browser tests: pages, map drill-down, filters, guided navigation, speed test,
insights/CSV, responsive layouts and automated accessibility (axe-core)."""
import json
import re
from urllib.parse import parse_qs, urlparse

import pytest
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect

from backend.extensions import db
from backend.models import Measurement
from tests.e2e.conftest import VIT

PAGES = ["/", "/map", "/speed-test", "/providers", "/insights", "/about", "/how-it-works", "/privacy"]

# TEST-ONLY stand-in for M-Lab's ndt7 client. It replaces /static/vendor/ndt7/ndt7.js in these
# tests only (real tests are never simulated in the app); it lets the page flow run offline.
NDT7_STAND_IN = """
window.ndt7 = { test: async (config, cb) => {
  if (config.userAcceptedDataPolicy !== true) throw new Error('policy not accepted');
  cb.serverChosen({ location: { city: 'Chennai', country: 'IN' } });
  cb.downloadMeasurement({ Source: 'client', Data: { MeanClientMbps: 20 } });
  cb.downloadComplete({ LastClientMeasurement: { MeanClientMbps: 38 },
                        LastServerMeasurement: { TCPInfo: { MinRTT: 45000, RTTVar: 8000 } } });
  cb.uploadMeasurement({ Source: 'server', Data: { TCPInfo: { BytesReceived: 7500000, ElapsedTime: 5000000 } } });
  cb.uploadComplete({ LastServerMeasurement: { TCPInfo: { BytesReceived: 15000000, ElapsedTime: 10000000 } } });
  return 0;
} };
"""

# Stand-in reply in the routing service's (OSRM) format.
ROUTE_STAND_IN = {"code": "Ok", "routes": [{"distance": 640.0, "duration": 480.0, "geometry": {
    "type": "LineString", "coordinates": [[VIT[1], VIT[0]], [VIT[1], VIT[0] + 0.002], [VIT[1], VIT[0] + 0.0045]]}}]}


def use_engine_stand_in(page, base_url):
    def handle(route):
        url = route.request.url
        if url.endswith("/static/vendor/ndt7/ndt7.js"):
            return route.fulfill(status=200, content_type="text/javascript", body=NDT7_STAND_IN)
        return route.continue_() if url.startswith(base_url) else route.abort()
    page.route("**/*", handle)


def wait_for_regions(page, count):
    # Element waits, not wait_for_function: the app's CSP (no 'unsafe-eval') blocks string evaluation.
    page.locator(".leaflet-regions-pane path").nth(count - 1).wait_for(state="attached")


def wait_for_states(page):
    wait_for_regions(page, 36)


@pytest.mark.parametrize("path", PAGES)
def test_pages_render_without_errors(offline, console_errors, base_url, path):
    response = offline.goto(base_url + path)
    assert response.status == 200
    offline.wait_for_load_state("networkidle")
    assert offline.locator(".sidebar__nav a").count() == 5
    assert console_errors == []


def test_map_drilldown_india_state_district(offline, console_errors, base_url):
    offline.goto(base_url + "/map")
    wait_for_states(offline)
    expect(offline.locator(".panel-title")).to_have_text("India")
    expect(offline.locator("#legend")).to_contain_text("No tests yet")
    expect(offline.locator("#legend")).to_contain_text("Not enough tests")

    offline.goto(base_url + "/map?area=IN-TN")
    expect(offline.locator(".panel-title")).to_have_text("Tamil Nadu")
    wait_for_regions(offline, 61)  # 36 states + Tamil Nadu's districts
    # Tamil Nadu has tests in only one district: the state itself must not get a score.
    expect(offline.locator("#panel-body .score-badge").first).to_have_text("Not enough tests")

    offline.locator(".region-item").first.click()
    expect(offline).to_have_url(re.compile(r"area=IN-TN-D\d+"))
    expect(offline.locator(".breadcrumb")).to_contain_text("Tamil Nadu")
    assert console_errors == []


def test_map_search_by_keyboard(offline, base_url):
    offline.goto(base_url + "/map")
    wait_for_states(offline)
    search = offline.get_by_role("combobox")
    search.fill("Chengalpattu")
    expect(offline.get_by_role("option").first).to_contain_text("Chengalpattu")
    search.press("Enter")
    expect(offline.locator(".panel-title")).to_have_text("Chengalpattu")


def test_map_filters_and_density_mode(offline, base_url):
    offline.goto(base_url + "/map?area=IN-TN")
    expect(offline.locator(".panel-title")).to_have_text("Tamil Nadu")
    offline.locator(".map-options summary").click()
    with offline.expect_response(lambda r: "/regions/IN-TN/stats" in r.url and "period=30" in r.url):
        offline.get_by_label("Time period").select_option("30")
    assert "period=30" in offline.url
    offline.get_by_label("Number of tests").check()
    expect(offline.locator("#legend")).to_contain_text("Few tests")


def test_guided_navigation(browser, base_url):
    context = browser.new_context(geolocation={"latitude": VIT[0], "longitude": VIT[1], "accuracy": 20},
                                  permissions=["geolocation"])
    page = context.new_page()
    requests = []

    def handle(route):
        url = route.request.url
        requests.append(url)
        if url.startswith(base_url):
            return route.continue_()
        if "routing.openstreetmap.de" in url:
            return route.fulfill(status=200, content_type="application/json", body=json.dumps(ROUTE_STAND_IN))
        if "tile.openstreetmap.org" in url:
            return route.fulfill(status=204)
        return route.abort()

    page.route("**/*", handle)
    page.goto(base_url + "/map")
    wait_for_states(page)
    page.get_by_role("button", name="Find a better connection nearby").click()
    items = page.locator(".nav-item")
    expect(items.first).to_contain_text("97/100")            # the good block ~500 m north
    expect(page.locator(".nav-section")).to_contain_text("not a guarantee")
    expect(items.first).to_contain_text("Based on 6 tests")

    nearby_calls = [u for u in requests if "/navigation/nearby" in u]
    query = parse_qs(urlparse(nearby_calls[-1]).query)
    assert len(query["cell"][0]) == 7 and "lat" not in query and "lng" not in query  # only the ~150 m area code

    items.first.get_by_role("button", name="Show walking route").click()
    expect(items.first.locator(".nav-item__route")).to_contain_text("Walking route: 640 m · about 8 min")
    expect(page.locator(".leaflet-control-attribution")).to_contain_text("FOSSGIS")
    context.close()


def test_speed_test_flow_and_submission(browser, base_url, live_server):
    context = browser.new_context(geolocation={"latitude": VIT[0], "longitude": VIT[1], "accuracy": 15},
                                  permissions=["geolocation"])
    page = context.new_page()
    use_engine_stand_in(page, base_url)
    with live_server["app"].app_context():
        before = db.session.query(Measurement).count()

    page.goto(base_url + "/speed-test")
    expect(page.locator("#provider-chip")).to_contain_text("Your provider: Jio")
    page.get_by_text("Add my result to the community map").click()
    with page.expect_request(lambda r: r.url.endswith("/api/v1/measurements") and r.method == "POST") as posted:
        page.get_by_role("button", name="Agree and start test").click()
    body = json.loads(posted.value.post_data)
    assert len(body["cell_id"]) == 7 and not {"lat", "lng", "latitude", "longitude"} & set(body)
    assert re.fullmatch(r"[0-9a-f-]{36}", body["submission_id"])

    expect(page.locator(".result-hero .score-ring__value")).to_have_text("74")   # 38/12/45/8
    expect(page.locator(".share-status")).to_contain_text("added to the community map")
    with live_server["app"].app_context():
        assert db.session.query(Measurement).count() == before + 1
    context.close()


def test_speed_test_without_sharing_sends_nothing(browser, base_url):
    context = browser.new_context()
    page = context.new_page()
    use_engine_stand_in(page, base_url)
    posts = []
    page.on("request", lambda r: posts.append(r.url) if r.method == "POST" else None)
    page.goto(base_url + "/speed-test")
    page.get_by_role("button", name="Agree and start test").click()
    expect(page.locator(".result-hero .score-ring__value")).to_have_text("74")
    assert posts == []
    context.close()


def test_providers_and_insights_with_csv(offline, base_url):
    offline.goto(base_url + "/providers?area=IN-TN")
    expect(offline.locator(".provider-card").first).to_be_visible()
    offline.goto(base_url + "/insights?area=IN-TN")
    expect(offline.get_by_text("Download a report")).to_be_visible()
    link = offline.get_by_role("link", name="By districts")
    response = offline.request.get(base_url + link.get_attribute("href"))
    assert response.ok and response.headers["content-type"].startswith("text/csv")
    assert response.text().splitlines()[0].startswith("area_code,area_name")


@pytest.mark.parametrize("width,height", [(360, 740), (390, 844), (768, 1024), (1024, 768), (1280, 800), (1440, 900)])
@pytest.mark.parametrize("path", PAGES)
def test_no_horizontal_scrolling(offline, base_url, width, height, path):
    offline.set_viewport_size({"width": width, "height": height})
    offline.goto(base_url + path)
    offline.wait_for_load_state("networkidle")
    overflow = offline.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    assert overflow <= 1, f"{path} at {width}px scrolls sideways by {overflow}px"


@pytest.mark.parametrize("path", PAGES + ["/map?area=IN-TN", "/insights?area=IN-TN"])
@pytest.mark.parametrize("width", [390, 1280])
def test_accessibility(offline, base_url, path, width):
    offline.set_viewport_size({"width": width, "height": 900})
    offline.goto(base_url + path)
    offline.wait_for_load_state("networkidle")
    results = Axe().run(offline)
    serious = [v for v in results.response["violations"] if v["impact"] in ("serious", "critical")]
    assert serious == [], json.dumps([{"id": v["id"], "help": v["help"],
                                       "nodes": [n["target"] for n in v["nodes"][:3]]} for v in serious], indent=1)


def test_sidebar_collapses_and_remembers(offline, base_url):
    offline.set_viewport_size({"width": 1440, "height": 900})
    offline.goto(base_url + "/insights")
    sidebar = offline.locator("#sidebar")
    toggle = offline.locator("#sidebar-toggle")
    expect(sidebar).to_have_attribute("data-collapsed", "false")
    expect(offline.locator(".sidebar__nav a[aria-current='page']")).to_contain_text("Insights")
    content_left = lambda: offline.locator(".app__content").bounding_box()["x"]  # noqa: E731
    wide = content_left()

    toggle.click()
    expect(sidebar).to_have_attribute("data-collapsed", "true")
    expect(toggle).to_have_attribute("aria-expanded", "false")
    offline.wait_for_timeout(400)
    assert content_left() < wide                                  # content uses the freed space
    link = offline.locator(".sidebar__nav a").first
    offline.keyboard.press("Tab")                                  # keyboard focus moves from the toggle to "Home"
    expect(link).to_be_focused()
    assert offline.evaluate("getComputedStyle(document.querySelector('.sidebar__nav a'), '::after').visibility") == "visible"
    assert link.get_attribute("data-tooltip") == "Home"

    offline.goto(base_url + "/providers")                         # the choice is remembered
    expect(offline.locator("#sidebar")).to_have_attribute("data-collapsed", "true")
    offline.locator("#sidebar-toggle").click()
    expect(offline.locator("#sidebar")).to_have_attribute("data-collapsed", "false")


def test_tablet_defaults_to_icon_rail(offline, base_url):
    offline.set_viewport_size({"width": 1024, "height": 768})
    offline.goto(base_url + "/")
    expect(offline.locator("#sidebar")).to_have_attribute("data-collapsed", "true")
    expect(offline.locator(".bottom-nav")).to_be_hidden()


def test_phone_menu_and_bottom_navigation(offline, base_url):
    offline.set_viewport_size({"width": 390, "height": 844})
    offline.goto(base_url + "/")
    expect(offline.locator("#sidebar")).to_be_hidden()
    expect(offline.locator(".bottom-nav a")).to_have_count(5)
    offline.get_by_role("button", name="More pages").click()
    menu = offline.locator("#menu-sheet")
    expect(menu).to_be_visible()
    menu.get_by_role("link", name="How it works").click()
    expect(offline).to_have_url(re.compile(r"/how-it-works$"))
    expect(offline.get_by_role("heading", level=1)).to_contain_text("From one speed test")


# TEST ONLY. Run 1 starts a real ndt7 worker (it connects nowhere until given URLs) and tries to
# deliver a late result 1.5 s after starting; run 2 completes normally (38/12/45/8 → score 74).
NDT7_CANCEL_STAND_IN = """
window.__runs = 0;
window.ndt7 = { test: async (config, cb) => {
  window.__runs += 1;
  const complete = () => {
    cb.downloadComplete({ LastClientMeasurement: { MeanClientMbps: 38 },
                          LastServerMeasurement: { TCPInfo: { MinRTT: 45000, RTTVar: 8000 } } });
    cb.uploadComplete({ LastServerMeasurement: { TCPInfo: { BytesReceived: 15000000, ElapsedTime: 10000000 } } });
  };
  cb.serverChosen({ location: { city: 'Chennai', country: 'IN' } });
  if (window.__runs === 1) {
    window.__worker = new Worker('/static/vendor/ndt7/ndt7-download-worker.js');
    cb.downloadMeasurement({ Source: 'client', Data: { MeanClientMbps: 12 } });
    await new Promise((r) => setTimeout(r, 1500));
    cb.downloadMeasurement({ Source: 'client', Data: { MeanClientMbps: 999 } });   // late, after cancel
    complete();
    return 0;
  }
  complete();
  return 0;
} };
"""

# Counts Worker.terminate() calls and keeps a handle on the browser's own Worker class.
WORKER_SPY = "window.__NativeWorker = window.Worker; window.__terminated = 0;" \
             "const t = Worker.prototype.terminate; Worker.prototype.terminate = function () { window.__terminated++; return t.call(this); };"


def test_speed_test_cancellation_is_complete(browser, base_url, live_server):
    context = browser.new_context(geolocation={"latitude": VIT[0], "longitude": VIT[1], "accuracy": 15},
                                  permissions=["geolocation"])
    page = context.new_page()
    page.add_init_script(WORKER_SPY)
    posts = []
    page.on("request", lambda r: posts.append(r.url) if r.method == "POST" else None)

    def handle(route):
        url = route.request.url
        if url.endswith("/static/vendor/ndt7/ndt7.js"):
            return route.fulfill(status=200, content_type="text/javascript", body=NDT7_CANCEL_STAND_IN)
        return route.continue_() if url.startswith(base_url) else route.abort()
    page.route("**/*", handle)
    with live_server["app"].app_context():
        before = db.session.query(Measurement).count()

    page.goto(base_url + "/speed-test")
    page.get_by_text("Add my result to the community map").click()      # sharing on: nothing may be sent on cancel
    page.get_by_role("button", name="Agree and start test").click()
    page.wait_for_function("() => window.__worker !== undefined")
    page.get_by_role("button", name="Cancel test").click()

    # Cancelled state, background worker terminated, browser's Worker class restored.
    expect(page.locator("#live-status")).to_contain_text("Test cancelled. Nothing was measured or saved.")
    assert page.evaluate("window.__terminated") >= 1
    assert page.evaluate("window.Worker === window.__NativeWorker")
    # The engine's late result (1.5 s) is ignored: no result screen, gauge untouched, nothing submitted.
    page.wait_for_timeout(2000)
    expect(page.locator('[data-step="results"]')).to_be_hidden()
    expect(page.locator('[data-step="intro"]')).to_be_visible()
    assert "999" not in page.locator("#gauge").inner_text()
    assert posts == []

    # Another test can start straight away and completes normally.
    with page.expect_request(lambda r: r.url.endswith("/api/v1/measurements") and r.method == "POST"):
        page.get_by_role("button", name="Agree and start test").click()
    expect(page.locator(".result-hero .score-ring__value")).to_have_text("74")
    expect(page.locator(".share-status")).to_contain_text("added to the community map")
    assert len(posts) == 1
    with live_server["app"].app_context():
        assert db.session.query(Measurement).count() == before + 1   # only the completed test was stored
    context.close()


def test_home_shows_real_overview_and_state_map(offline, base_url):
    offline.goto(base_url + "/")
    expect(offline.locator("#overview .stat-tile").first).not_to_have_class(re.compile("skeleton"))
    expect(offline.locator("#overview")).to_contain_text("Tests shared")
    offline.locator("#home-map path.leaflet-interactive").nth(35).wait_for(state="attached")  # 36 states drawn
    search = offline.get_by_role("combobox")
    search.fill("Chennai")
    expect(offline.get_by_role("option").first).to_be_visible()


def test_insights_sections_in_order(offline, base_url):
    offline.goto(base_url + "/insights?area=IN-TN")
    titles = offline.locator(".insight-card__title")
    expect(titles.first).to_have_text("How neighbourhoods compare")
    texts = [t.strip() for t in titles.all_inner_texts()]
    order = ["How neighbourhoods compare", "Connection quality over time", "Measurement density",
             "Provider comparison", "Weak connectivity areas"]
    assert [t for t in texts if t in order] == order
    assert texts[-1] == "Download a report"
