"""Health, regions, search and locate."""
from flask import request
from sqlalchemy import case, or_, select, text
from sqlalchemy.exc import SQLAlchemyError

from ...extensions import db
from ...models import REGION_LEVELS, Region
from ...services import geo_lookup
from ...utils import geohash
from ...utils.responses import ApiError, ok
from . import api_v1
from .areas import get_region_or_404

SEARCH_LIMIT = 8


@api_v1.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise ApiError("service_unavailable", "The database is not reachable.", 503)
    return ok({"status": "ok", "database": "ok"})


@api_v1.get("/regions")
def list_regions():
    query = select(Region).order_by(Region.name)

    level = request.args.get("level")
    if level is not None:
        if level not in REGION_LEVELS:
            raise ApiError(
                "invalid_parameter",
                "Unknown region level.",
                400,
                {"level": f"Must be one of: {', '.join(REGION_LEVELS)}"},
            )
        query = query.where(Region.level == level)

    parent_code = request.args.get("parent")
    if parent_code is not None:
        query = query.where(Region.parent_id == get_region_or_404(parent_code).id)

    regions = db.session.scalars(query).all()
    return ok([r.to_summary() for r in regions], meta={"count": len(regions)})


@api_v1.get("/regions/<code>")
def region_detail(code: str):
    return ok(get_region_or_404(code).to_detail())


@api_v1.get("/search")
def search():
    """Find states, districts and cities by name. Runs entirely on our own data."""
    pattern = (request.args.get("q") or "").replace("%", "").replace("_", "").strip()
    if len(pattern) < 2:
        return ok([], meta={"count": 0})
    level_order = case({"state": 0, "district": 1, "city": 2, "country": 3}, value=Region.level)
    starts = Region.name.ilike(f"{pattern}%")
    query = (
        select(Region)
        .where(or_(starts, Region.name.ilike(f"% {pattern}%")))
        .order_by(case((starts, 0), else_=1), level_order, Region.population.desc().nulls_last(), Region.name)
        .limit(SEARCH_LIMIT)
    )
    results = [r.to_place() for r in db.session.scalars(query)]
    return ok(results, meta={"count": len(results)})


@api_v1.get("/locate")
def locate():
    """Which state/district/city is this ~150 m block in? Receives only the block code."""
    cell = (request.args.get("cell") or "").lower()
    if not geohash.is_valid(cell, geohash.BLOCK_PRECISION):
        raise ApiError("invalid_parameter", "That area code isn't valid.", 400,
                       {"cell": "Must be a 7-character area code."})
    location = geo_lookup.locate(*geohash.center(cell))
    if location is None:
        raise ApiError("outside_service_area", "That location is outside India.", 404)
    places = [get_region_or_404(c).to_place()
              for c in (location.state_code, location.district_code, location.city_code) if c]
    return ok({"cell_id": cell, "neighbourhood": cell[:6], "places": places})
