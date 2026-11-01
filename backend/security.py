"""HTTP security headers added to every response.

The Content-Security-Policy only allows our own scripts and styles. External
hosts are listed one by one, only where a feature needs them:
  - tile.openstreetmap.org: street-map tiles (from district zoom level down)
  - M-Lab (locate.measurementlab.net, *.measurement-lab.org): the speed test
  - routing.openstreetmap.de (FOSSGIS): walking routes, only when the user asks for one
"""
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data: https://tile.openstreetmap.org",
        "font-src 'self'",
        "connect-src 'self' https://locate.measurementlab.net wss://*.measurement-lab.org https://routing.openstreetmap.de",
        "worker-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)


def static_headers(headers, _path, _url) -> None:
    """Headers for static files served by WhiteNoise (which bypasses Flask's after_request)."""
    headers["X-Content-Type-Options"] = "nosniff"
    headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY  # also applies to the speed-test workers


def register(app) -> None:
    @app.before_request
    def require_https():
        # Behind a proxy, ProxyFix makes request.scheme reflect the visitor's original scheme.
        from flask import redirect, request
        if app.config["FORCE_HTTPS"] and request.scheme != "https" and request.path != "/api/health":
            return redirect(request.url.replace("http://", "https://", 1), code=301)
        return None

    @app.after_request
    def set_security_headers(response):
        headers = response.headers
        headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        # Location may only ever be requested by our own pages.
        headers.setdefault("Permissions-Policy", "geolocation=(self), camera=(), microphone=(), payment=()")
        if app.config.get("HSTS_ENABLED"):
            headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response
