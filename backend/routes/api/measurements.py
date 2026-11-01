"""Submitting a speed-test result (only ever with the user's consent) and listing results."""
from flask import current_app, request

from ...extensions import limiter
from ...services import measurements, nqi
from ...utils.client_ip import client_ip
from ...utils.responses import ApiError, ok
from . import api_v1
from .areas import parse_filters, resolve_area

FLAG_MESSAGES = {
    "vpn_or_hosting": "This result was measured through a VPN or cloud network, so it isn't counted in area scores.",
    "implausible": "This result looked unusual, so it isn't counted in area scores.",
}


@api_v1.post("/measurements")
# Shared bucket, so /api and /api/v1 can't be alternated to double the limit.
@limiter.shared_limit(lambda: current_app.config["MEASUREMENT_RATE_LIMIT"], scope="measurements")
def create_measurement():
    m, identification = measurements.create(request.get_json(silent=True), client_ip())
    score = round(m.nqi)
    return ok({
        "id": m.id,
        "score": score,
        "band": nqi.band(score),
        "nqi": m.nqi,
        "tested_at": m.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cell_id": m.cell_id,
        "neighbourhood": m.cell_id[:6],
        "state_code": m.state_code,
        "district_code": m.district_code,
        "city_code": m.city_code,
        "provider": identification.to_public(),
        "counted": not m.flagged,
        "message": FLAG_MESSAGES.get(m.flag_reason),
    }, status=201)


def _int_arg(name: str, default: int | None, minimum: int, maximum: int | None = None) -> int | None:
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ApiError("invalid_parameter", f"'{name}' must be a whole number.", 400, {name: "Not a number."}) from None
    if value < minimum or (maximum is not None and value > maximum):
        raise ApiError("invalid_parameter", f"'{name}' is out of range.", 400,
                       {name: f"Must be between {minimum} and {maximum}." if maximum else f"Must be at least {minimum}."})
    return value


@api_v1.get("/measurements")
def list_measurements():
    """Recent counted tests, newest first. Locations are coarse (see services/measurements.py)."""
    region, cell = None, None
    if request.args.get("area"):
        kind, area = resolve_area(request.args["area"])
        region, cell = (area, None) if kind == "region" else (None, area)
    filters = parse_filters()
    limit = _int_arg("limit", 50, 1, measurements.LIST_MAX_LIMIT)
    before = _int_arg("before", None, 1)
    items, next_cursor = measurements.list_public(region=region, cell=cell, filters=filters,
                                                  limit=limit, before_id=before)
    return ok(items, meta={"count": len(items), "next_before": next_cursor, "filters": filters.to_public()})
