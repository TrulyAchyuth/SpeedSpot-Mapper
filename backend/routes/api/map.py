"""Map layers: state and district choropleths, and grid cells in view."""
from flask import request

from ...services import stats, stats_cache
from ...utils import geohash
from ...utils.responses import ApiError, ok
from . import api_v1
from .areas import get_region_or_404, parse_filters

# Largest map area (degrees of latitude/longitude) for which cells are returned.
MAX_SPAN = {geohash.NEIGHBOURHOOD_PRECISION: 4.0, geohash.BLOCK_PRECISION: 0.6}


def parse_bbox(value: str | None) -> list[float]:
    try:
        south, west, north, east = (float(v) for v in (value or "").split(","))
    except ValueError:
        raise ApiError("invalid_parameter", "The map area wasn't understood.", 400,
                       {"bbox": "Expected 'south,west,north,east'."}) from None
    if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise ApiError("invalid_parameter", "The map area wasn't understood.", 400,
                       {"bbox": "Coordinates out of range."})
    return [south, west, north, east]


@api_v1.get("/map/states")
def map_states():
    """All 36 states/UTs with their (cached) summaries, for colouring the national map."""
    filters = parse_filters()
    india = get_region_or_404("IN")
    states = (stats_cache.children_summaries(india) if filters.is_default
              else stats.children_stats(india, stats.rows_for_region(india, filters)))
    return ok(states, meta={"count": len(states), "filters": filters.to_public()})


@api_v1.get("/map/districts")
def map_districts():
    code = request.args.get("state")
    if not code:
        raise ApiError("invalid_parameter", "Please choose a state.", 400, {"state": "Required, e.g. IN-TN."})
    state = get_region_or_404(code)
    if state.level != "state":
        raise ApiError("invalid_parameter", "That isn't a state or union territory.", 400, {"state": "Must be a state code."})
    filters = parse_filters()
    districts = (stats_cache.children_summaries(state) if filters.is_default
                 else stats.children_stats(state, stats.rows_for_region(state, filters)))
    return ok(districts, meta={"count": len(districts), "state": state.code, "filters": filters.to_public()})


@api_v1.get("/map/cells")
@api_v1.get("/cells")
def map_cells():
    try:
        precision = int(request.args.get("precision", geohash.NEIGHBOURHOOD_PRECISION))
    except ValueError:
        precision = -1
    if precision not in MAX_SPAN:
        raise ApiError("invalid_parameter", "Unknown detail level.", 400, {"precision": "Must be 6 or 7."})
    bbox = parse_bbox(request.args.get("bbox"))
    filters = parse_filters()
    if bbox[2] - bbox[0] > MAX_SPAN[precision] or bbox[3] - bbox[1] > MAX_SPAN[precision]:
        raise ApiError("area_too_large", "Zoom in a little to see this level of detail.", 400)
    features = stats.cells_in_bbox(bbox, precision, filters)
    return ok(features, meta={"count": len(features), "precision": precision, "filters": filters.to_public()})
