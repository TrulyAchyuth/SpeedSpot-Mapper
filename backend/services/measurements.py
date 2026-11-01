"""Validating, storing and listing speed tests."""
import re
from collections import Counter
from datetime import datetime

from sqlalchemy import func, literal_column, select

from ..extensions import db
from ..models import Measurement, Provider
from ..models.measurement import CONNECTION_TYPES
from ..utils import geohash
from ..utils.clock import hour_now
from ..utils.responses import ApiError
from . import grid, nqi, providers, stats, stats_cache

ENGINES = ("mlab-ndt7",)
MAX_SPEED_MBPS = 10_000  # 10 Gbps — far beyond any consumer connection in India
MAX_TIME_MS = 10_000

# Physically possible but suspicious enough to keep out of scores.
SUSPICIOUS_DOWNLOAD_MBPS = 3_000
SUSPICIOUS_UPLOAD_MBPS = 3_000
SUSPICIOUS_MIN_LATENCY_MS = 1

# A neighbourhood is only shown next to an individual test once it has this many tests.
LIST_MIN_NEIGHBOURHOOD_TESTS = 5
LIST_MAX_LIMIT = 100

UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


def _number(payload: dict, field: str, minimum: float, maximum: float, errors: dict,
            exclusive_min: bool = False) -> float | None:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:  # NaN
        errors[field] = "Must be a number."
        return None
    if value < minimum or value > maximum or (exclusive_min and value == minimum):
        errors[field] = f"Must be {'more than' if exclusive_min else 'at least'} {minimum} and at most {maximum}."
        return None
    return float(value)


def validate(payload) -> dict:
    """Return clean values or raise ApiError(400) listing every problem."""
    if not isinstance(payload, dict):
        raise ApiError("validation_error", "Please send the result as a JSON object.", 400)
    errors = {}
    cell = payload.get("cell_id")
    if not geohash.is_valid(cell, geohash.BLOCK_PRECISION):
        errors["cell_id"] = "Must be a 7-character area code."
    clean = {
        "cell_id": cell,
        "download_mbps": _number(payload, "download_mbps", 0, MAX_SPEED_MBPS, errors, exclusive_min=True),
        "upload_mbps": _number(payload, "upload_mbps", 0, MAX_SPEED_MBPS, errors, exclusive_min=True),
        "latency_ms": _number(payload, "latency_ms", 0, MAX_TIME_MS, errors, exclusive_min=True),
        "jitter_ms": _number(payload, "jitter_ms", 0, MAX_TIME_MS, errors),
        "engine": payload.get("engine"),
        "connection_type": payload.get("connection_type", "unknown"),
        "submission_id": payload.get("submission_id"),
    }
    if clean["submission_id"] is not None and not (
            isinstance(clean["submission_id"], str) and UUID_PATTERN.match(clean["submission_id"])):
        errors["submission_id"] = "Must be a random (version 4) UUID in lower case."
    if clean["engine"] not in ENGINES:
        errors["engine"] = f"Must be one of: {', '.join(ENGINES)}"
    if clean["connection_type"] not in CONNECTION_TYPES:
        errors["connection_type"] = f"Must be one of: {', '.join(CONNECTION_TYPES)}"
    if errors:
        raise ApiError("validation_error", "Some of the test result didn't look right.", 400, errors)
    return clean


def flag_reason(values: dict, identification: providers.Identification) -> str | None:
    """Why a stored result should be kept out of scores (None = it counts)."""
    if not identification.counts_towards_scores:
        return "vpn_or_hosting"
    if (values["download_mbps"] > SUSPICIOUS_DOWNLOAD_MBPS or values["upload_mbps"] > SUSPICIOUS_UPLOAD_MBPS
            or values["latency_ms"] < SUSPICIOUS_MIN_LATENCY_MS):
        return "implausible"
    return None


def create(payload, ip: str | None) -> tuple[Measurement, providers.Identification]:
    values = validate(payload)
    if values["submission_id"] and db.session.scalar(
            select(Measurement.id).where(Measurement.submission_id == values["submission_id"])):
        raise ApiError("duplicate_submission", "This test result has already been received.", 409)
    block = grid.ensure_block(values["cell_id"])
    if block is None:
        raise ApiError("outside_service_area", "SpeedSpot currently maps tests taken in India only.", 422)

    identification = providers.identify(ip)  # the IP is used here, in memory, and then discarded
    reason = flag_reason(values, identification)
    measurement = Measurement(
        created_at=hour_now(), cell_id=block.cell_id, cell_lat=block.center_lat, cell_lng=block.center_lng,
        state_code=block.state_code, district_code=block.district_code, city_code=block.city_code,
        download_mbps=values["download_mbps"], upload_mbps=values["upload_mbps"],
        latency_ms=values["latency_ms"], jitter_ms=values["jitter_ms"],
        nqi=nqi.calculate(values["download_mbps"], values["upload_mbps"], values["latency_ms"], values["jitter_ms"]),
        provider_id=identification.provider.id if identification.provider else None,
        provider_status=identification.status, asn=identification.asn, asn_org=identification.asn_org,
        connection_type=values["connection_type"], engine=values["engine"], source="user",
        flagged=reason is not None, flag_reason=reason, submission_id=values["submission_id"],
    )
    db.session.add(measurement)
    stats_cache.invalidate_block(block.cell_id, block.state_code, block.district_code, block.city_code)
    db.session.commit()
    return measurement, identification


# ---------- Public listing ----------

def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def list_public(*, region=None, cell: str | None = None, filters: stats.Filters = stats.DEFAULT_FILTERS,
                limit: int = 50, before_id: int | None = None) -> tuple[list[dict], int | None]:
    """Recent counted tests, newest first, with coarse locations only.

    Each item shows its ~1 km neighbourhood only when that neighbourhood already has
    LIST_MIN_NEIGHBOURHOOD_TESTS visible tests; otherwise just the district, so a single
    household's test can't be pinpointed.
    """
    query = select(Measurement, Provider).outerjoin(Provider).where(*stats.base_conditions(filters))
    if region is not None and region.level != "country":
        query = query.where(getattr(Measurement, stats.LEVEL_COLUMN[region.level]) == region.code)
    if cell:
        query = query.where(Measurement.cell_id.like(f"{cell}%"))
    if before_id:
        query = query.where(Measurement.id < before_id)
    rows = db.session.execute(query.order_by(Measurement.id.desc()).limit(limit + 1)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    neighbourhoods = {m.cell_id[:6] for m, _ in rows}
    counts = Counter()
    if neighbourhoods:
        # Inline constants: PostgreSQL only accepts GROUP BY on an expression identical to the SELECT one,
        # and bound parameters would make the two look different.
        prefix = func.substr(Measurement.cell_id, literal_column("1"), literal_column("6"))
        count_query = (select(prefix, func.count())
                       .where(*stats.base_conditions(), prefix.in_(neighbourhoods))
                       .group_by(prefix))
        counts.update(dict(db.session.execute(count_query).all()))

    items = []
    for m, provider in rows:
        score = round(m.nqi)
        neighbourhood = m.cell_id[:6]
        items.append({
            "id": m.id,
            "tested_at": _iso(m.created_at),  # rounded to the hour
            "download_mbps": m.download_mbps, "upload_mbps": m.upload_mbps,
            "latency_ms": m.latency_ms, "jitter_ms": m.jitter_ms,
            "score": score, "band": nqi.band(score),
            "provider": provider.to_summary() if provider else None,
            "provider_status": m.provider_status,
            "connection_type": m.connection_type,
            "neighbourhood": neighbourhood if counts[neighbourhood] >= LIST_MIN_NEIGHBOURHOOD_TESTS else None,
            "state_code": m.state_code, "district_code": m.district_code,
        })
    next_cursor = rows[-1][0].id if has_more and rows else None
    return items, next_cursor
