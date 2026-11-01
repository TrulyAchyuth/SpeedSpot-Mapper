"""Read-through cache of area summaries, stored in the `area_statistics` table.

summary(level, code, compute)      one area; compute() runs only on a cache miss
summaries(level, codes, compute)   many areas (e.g. all 36 states for the map) in one go
invalidate_block(block_id, loc)    drop every area a new test belongs to
invalidate_all()                   drop everything (e.g. `flask stats clear-cache`)
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from flask import current_app
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import AreaStatistic
from . import stats

COUNTRY = "IN"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse(iso: str | None) -> datetime | None:
    return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ") if iso else None


def _to_summary(row: AreaStatistic) -> dict:
    medians = None
    if row.status == "ok":
        medians = {"download_mbps": row.median_download_mbps, "upload_mbps": row.median_upload_mbps,
                   "latency_ms": round(row.median_latency_ms), "jitter_ms": row.median_jitter_ms}
    return {
        "status": row.status, "score": row.score, "band": row.band,
        "sample_count": row.sample_count, "neighbourhood_count": row.neighbourhood_count,
        "block_count": row.block_count, "district_count": row.district_count,
        "last_updated": stats.iso(row.last_measurement_at), "medians": medians,
        "requirement": stats.requirement(row.area_level),
    }


def _store(level: str, code: str, summary: dict) -> None:
    medians = summary["medians"] or {}
    db.session.add(AreaStatistic(
        area_level=level, area_code=code, status=summary["status"], score=summary["score"],
        band=summary["band"], sample_count=summary["sample_count"],
        neighbourhood_count=summary["neighbourhood_count"], block_count=summary["block_count"],
        district_count=summary["district_count"], median_download_mbps=medians.get("download_mbps"),
        median_upload_mbps=medians.get("upload_mbps"), median_latency_ms=medians.get("latency_ms"),
        median_jitter_ms=medians.get("jitter_ms"),
        last_measurement_at=_parse(summary["last_updated"]), computed_at=_now(),
    ))


def _fresh_rows(level: str, codes: list[str]) -> dict[str, AreaStatistic]:
    cutoff = _now() - timedelta(minutes=current_app.config["STATS_CACHE_TTL_MINUTES"])
    rows = db.session.scalars(select(AreaStatistic).where(
        AreaStatistic.area_level == level, AreaStatistic.area_code.in_(codes)))
    found = {}
    for row in rows:
        if row.computed_at >= cutoff:
            found[row.area_code] = row
        else:
            db.session.delete(row)
    return found


def summaries(level: str, codes: list[str], compute) -> dict[str, dict]:
    """compute(missing_codes) -> {code: summary} for the codes not in the cache."""
    found = _fresh_rows(level, codes)
    result = {code: _to_summary(row) for code, row in found.items()}
    missing = [c for c in codes if c not in found]
    if missing:
        db.session.flush()  # stale rows are gone before re-inserting
        computed = compute(missing)
        for code in missing:
            result[code] = computed[code]
            _store(level, code, computed[code])
    try:
        db.session.commit()
    except IntegrityError:
        # Another request cached the same areas at the same moment. Both computed the same
        # values from the same data, so keep ours for this response and let theirs stand.
        db.session.rollback()
    return result


def summary(level: str, code: str, compute) -> dict:
    return summaries(level, [code], lambda _missing: {code: compute()})[code]


def invalidate_block(block_id: str, state_code: str, district_code: str, city_code: str | None) -> None:
    codes = [COUNTRY, state_code, district_code, block_id, block_id[:6]] + ([city_code] if city_code else [])
    db.session.execute(delete(AreaStatistic).where(AreaStatistic.area_code.in_(codes)))


def invalidate_all() -> None:
    db.session.execute(delete(AreaStatistic))
    db.session.commit()


# ---------- Composed helpers used by the API ----------

CHILD_LEVEL = {"country": "state", "state": "district"}


def region_summary(region, load_rows) -> dict:
    """Cached summary of one region; load_rows() is called only on a cache miss."""
    return summary(region.level, region.code, lambda: stats.summarize(load_rows(), region.level))


def children_summaries(region) -> list[dict]:
    """Every state of India, or every district of a state, with its cached summary."""
    child_level = CHILD_LEVEL[region.level]
    column = stats.CHILD_COLUMN[region.level]
    children = list(region.children)

    def compute(missing: list[str]) -> dict[str, dict]:
        groups = defaultdict(list)
        for row in stats.rows_for_region(region):
            groups[getattr(row, column)].append(row)
        return {code: stats.summarize(groups.get(code, []), child_level) for code in missing}

    result = summaries(child_level, [c.code for c in children], compute)
    return [{**c.to_summary(), "bbox": c.bbox(), "summary": result[c.code]} for c in children]
