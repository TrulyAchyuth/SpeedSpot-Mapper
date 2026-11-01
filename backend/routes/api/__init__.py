"""Versioned JSON API: /api/v1/... (conventions in docs/API.md).

The same blueprint is also mounted at /api/... (see create_app), so /api/health and
/api/v1/health are the same endpoint. /api always means "the current version".

Modules: core (health, regions, search, locate), map (map layers), stats (area
statistics), measurements (submit and list tests), providers (providers and the
visitor's own provider).
"""
from flask import Blueprint

api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")

from . import core, map, measurements, providers, stats  # noqa: E402,F401  (attach routes)
