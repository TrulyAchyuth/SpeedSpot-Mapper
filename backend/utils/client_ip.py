"""The visitor's IP address — used only in memory, for provider lookup and rate limiting.

Behind a reverse proxy, set TRUSTED_PROXY_COUNT so werkzeug's ProxyFix reads the real
address from X-Forwarded-For (configured in create_app). Never trust that header otherwise.
"""
from flask import current_app, request


def client_ip() -> str | None:
    override = current_app.config.get("DEV_CLIENT_IP")
    # Lets developers test provider detection from localhost. Ignored in production.
    if override and current_app.config["ENV_NAME"] in ("development", "testing"):
        return override
    return request.remote_addr
