"""Shared helpers: turning an `area` parameter into a region or a grid cell, and parsing filters."""
from flask import current_app, request

from ...extensions import db
from ...models import Provider
from ...services.stats import PERIODS, Filters
from ...models import Region
from ...services import geo_lookup
from ...services.regions import get_region
from ...utils import geohash
from ...utils.responses import ApiError


def get_region_or_404(code: str) -> Region:
    region = get_region(code)
    if region is None:
        raise ApiError("not_found", f"No region with code '{code}'.", 404)
    return region


def valid_cell_or_400(cell: str) -> str:
    cell = (cell or "").lower()
    if not (geohash.is_valid(cell) and len(cell) in (geohash.NEIGHBOURHOOD_PRECISION, geohash.BLOCK_PRECISION)):
        raise ApiError("invalid_parameter", "That area code isn't valid.", 400,
                       {"cell": "Must be a 6- or 7-character area code."})
    return cell


def cell_level(cell: str) -> str:
    return "block" if len(cell) == geohash.BLOCK_PRECISION else "neighbourhood"


def cell_place(cell: str) -> dict:
    """Describe a grid cell the same way a region is described."""
    south, west, north, east = geohash.bounds(cell)
    lat, lng = (south + north) / 2, (west + east) / 2
    location = geo_lookup.locate(lat, lng)
    breadcrumb, near = [], None
    if location:
        codes = [c for c in ("IN", location.state_code, location.district_code, location.city_code) if c]
        regions = [get_region(c) for c in codes]
        breadcrumb = [r.to_summary() for r in regions if r]
        near = regions[-1].name if regions and regions[-1] else None
    level = cell_level(cell)
    noun = "Block" if level == "block" else "Neighbourhood"
    return {
        "code": cell, "name": f"{noun} near {near}" if near else noun, "level": level, "kind": level,
        "label": f"Area about {'150 m' if level == 'block' else '1 km'} across",
        "bbox": [south, west, north, east], "center": [lat, lng], "breadcrumb": breadcrumb,
    }


def resolve_area(value: str | None):
    """Return ("region", Region) or ("cell", geohash)."""
    if not value:
        raise ApiError("invalid_parameter", "Please choose an area.", 400, {"area": "Required."})
    if value.upper().startswith("IN"):
        return "region", get_region_or_404(value)
    return "cell", valid_cell_or_400(value)


def region_place(region: Region) -> dict:
    return {**region.to_place(), "breadcrumb": [r.to_summary() for r in region.breadcrumb()]}


def parse_filters(*, allow_provider: bool = True):
    """?period=7|30|90|180 (days) and ?provider=<slug>|unidentified → stats.Filters."""
    period_days = None
    raw_period = request.args.get("period")
    if raw_period:
        try:
            value = int(raw_period.rstrip("d"))
        except ValueError:
            value = -1
        if value not in PERIODS:
            raise ApiError("invalid_parameter", "Unknown time period.", 400,
                           {"period": f"Must be one of: {', '.join(map(str, PERIODS))} (days)."})
        # The full window is the default, which keeps cached results usable.
        period_days = None if value == current_app.config["FRESHNESS_WINDOW_DAYS"] else value

    raw_provider = request.args.get("provider")
    if raw_provider and not allow_provider:
        raise ApiError("invalid_parameter", "The provider filter can't be used here.", 400,
                       {"provider": "Not supported on this endpoint."})
    if raw_provider == "unidentified":
        return Filters(period_days=period_days, unidentified=True)
    if raw_provider:
        provider = db.session.query(Provider).filter_by(slug=raw_provider).first()
        if provider is None:
            raise ApiError("not_found", f"No provider called '{raw_provider}'.", 404)
        return Filters(period_days=period_days, provider_id=provider.id, provider_slug=provider.slug)
    return Filters(period_days=period_days)
