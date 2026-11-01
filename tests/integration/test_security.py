import pytest

from backend import create_app
from tests.conftest import PROD_OVERRIDES


@pytest.mark.parametrize("path", ["/", "/api/v1/health", "/does-not-exist"])
def test_security_headers_on_every_response(client, path):
    headers = client.get(path).headers
    csp = headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "geolocation=(self)" in headers["Permissions-Policy"]
    # Only the specific external hosts features need:
    assert "https://tile.openstreetmap.org" in csp
    assert "wss://*.measurement-lab.org" in csp
    assert "unsafe-inline" not in csp


def test_hsts_only_in_production(client):
    assert "Strict-Transport-Security" not in client.get("/").headers
    prod = create_app("production", PROD_OVERRIDES)
    assert "max-age=" in prod.test_client().get("/", base_url="https://localhost").headers["Strict-Transport-Security"]


def test_production_redirects_http_to_https():
    client = create_app("production", PROD_OVERRIDES).test_client()
    response = client.get("/map?area=IN-TN")
    assert response.status_code == 301
    assert response.headers["Location"] == "https://localhost/map?area=IN-TN"
    assert client.get("/api/health").status_code != 301  # health checks may use plain HTTP


def test_no_cors_headers_are_sent(client):
    """The API is same-origin only: other websites' scripts can't read it."""
    for path in ("/api/health", "/api/map/states"):
        response = client.get(path, headers={"Origin": "https://evil.example"})
        assert "Access-Control-Allow-Origin" not in response.headers
    preflight = client.options("/api/measurements", headers={
        "Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "Access-Control-Allow-Origin" not in preflight.headers


def test_oversized_requests_are_refused(client):
    response = client.post("/api/measurements", data="x" * (70 * 1024), content_type="application/json")
    assert response.status_code == 413
    assert response.get_json()["error"]["code"] == "payload_too_large"


def test_server_errors_do_not_leak_details(app):
    @app.get("/boom")
    def boom():
        raise RuntimeError("secret internal detail")

    response = app.test_client().get("/boom")
    assert response.status_code == 500
    assert "secret internal detail" not in response.get_data(as_text=True)
