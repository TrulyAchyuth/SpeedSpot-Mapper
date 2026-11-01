"""Gunicorn settings for production (`gunicorn -c gunicorn.conf.py wsgi:app`).

Privacy: access logging is OFF, because a standard access log would write every
visitor's IP address to disk. Errors are still logged (without request IPs).
"""
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"
# Each worker loads the district boundaries (~100 MB). One worker with threads fits
# Render's free/starter memory; raise WEB_CONCURRENCY on bigger instances.
workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
timeout = 60
graceful_timeout = 30
accesslog = None          # never log visitor IPs
errorlog = "-"
loglevel = "info"
# Render's proxy sets X-Forwarded-Proto; Flask's ProxyFix (TRUSTED_PROXY_COUNT) handles the rest.
forwarded_allow_ips = "*"
preload_app = True        # load boundaries once before forking
