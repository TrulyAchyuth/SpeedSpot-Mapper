import pytest

from backend.routes.pages import NAV_ITEMS

PAGES = [
    ("/", "Your city. Your connection.", "home"),
    ("/map", "Explore India", "map"),
    ("/speed-test", "How fast is your internet?", "speedtest"),
    ("/providers", "Which provider works best here?", "providers"),
    ("/insights", "Neighbourhood insights", "insights"),
    ("/privacy", "Your privacy comes first", None),
]


@pytest.mark.parametrize("path,expected_text,script", PAGES)
def test_page_renders(client, path, expected_text, script):
    response = client.get(path)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert expected_text in html
    assert '<html lang="en-IN">' in html
    assert 'name="viewport"' in html
    assert 'href="#main"' in html  # skip link for keyboard users
    assert 'id="location-dialog"' in html
    if script:
        assert f"js/pages/{script}.js" in html


def test_home_has_the_required_copy_and_actions(client):
    html = client.get("/").get_data(as_text=True)
    assert "Discover internet quality around you. Compare providers, explore connected neighbourhoods and help make your city smarter." in html
    assert "Explore India" in html and "Start Speed Test" in html


def test_navigation_has_the_five_required_items_in_order():
    assert [item.label for item in NAV_ITEMS] == [
        "Home", "Explore India", "Speed Test", "Compare Providers", "Insights",
    ]


def test_current_page_is_marked_for_screen_readers(client):
    html = client.get("/map").get_data(as_text=True)
    import re
    # Sidebar + phone bottom bar both mark the current page.
    assert len(re.findall(r'href="/map"[^>]*aria-current="page"', html)) == 2
    assert not re.findall(r'href="/"[^>]*aria-current="page"', html)


def test_map_page_loads_leaflet_locally(client):
    html = client.get("/map").get_data(as_text=True)
    assert "/static/vendor/leaflet/leaflet.js" in html
    assert "unpkg.com" not in html and "cdn" not in html.lower()


def test_speed_test_discloses_mlab_before_starting(client):
    html = client.get("/speed-test").get_data(as_text=True)
    assert "M-Lab publishes every test, including your IP address" in html
    assert "Agree and start test" in html
    assert 'id="share-toggle"' in html and "checked" not in html.split('id="share-toggle"')[1][:20]


def test_pages_use_no_inline_scripts_or_styles(client):
    for path, _, _ in PAGES:
        html = client.get(path).get_data(as_text=True)
        assert "<script>" not in html
        assert "style=" not in html


@pytest.mark.parametrize("path", ["/", "/map", "/speed-test", "/providers", "/insights", "/about", "/how-it-works", "/privacy"])
def test_no_demo_banner_or_labels_on_any_page(client, add_tests, path):
    add_tests(12.84, 80.15, 3)
    html = client.get(path).get_data(as_text=True).lower()
    assert "demo-banner" not in html and "demo data" not in html and "generated test data" not in html


def test_unknown_page_shows_friendly_html_404(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert response.mimetype == "text/html"
    assert "Page not found" in response.get_data(as_text=True)


@pytest.mark.parametrize("path", [
    "/static/css/tokens.css", "/static/css/map.css", "/static/js/pages/map.js",
    "/static/geo/states.geojson", "/static/geo/districts/IN-TN.geojson",
    "/static/vendor/ndt7/ndt7-download-worker.js", "/static/fonts/inter-latin-wght-normal.woff2",
])
def test_static_assets_are_served(client, path):
    response = client.get(path)
    assert response.status_code == 200
    response.close()


def test_design_tokens_contain_brand_palette(client):
    css = client.get("/static/css/tokens.css").get_data(as_text=True)
    for colour in ["#F7F8F5", "#DCE9DF", "#638B72", "#263B32", "#E9EDE8"]:
        assert colour in css
