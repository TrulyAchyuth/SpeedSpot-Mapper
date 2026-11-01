"""Aggregating measurements into honest area scores.

The core rule: an area only gets a score when there is enough data, spread widely
enough, to represent it. A whole state is never coloured "Good" because one
neighbourhood had a few fast tests. Scores are medians of the underlying tests,
never medians of medians. "No data" (no tests) and "weak" (tested and slow) are
always different things.

Every query can be narrowed with `Filters` (time period, provider).
"""
import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from statistics import median

from flask import current_app
from sqlalchemy import select

from ..extensions import db
from ..models import Measurement, Provider, Region
from ..utils import geohash
from ..utils.clock import hour_now
from . import nqi


@dataclass(frozen=True)
class Rule:
    min_samples: int
    min_neighbourhoods: int = 1
    min_districts: int = 1


# Tunable during the pilot. Documented in docs/GEOSPATIAL.md §5.
RULES = {
    "block": Rule(5),
    "neighbourhood": Rule(5),
    "city": Rule(20, min_neighbourhoods=3),
    "district": Rule(30, min_neighbourhoods=5),
    "state": Rule(100, min_neighbourhoods=15, min_districts=3),
    "country": Rule(300, min_neighbourhoods=40, min_districts=8),
}
PROVIDER_MIN_SAMPLES = 5           # per provider, per area
TREND_MIN_SAMPLES = 5              # per time bucket
TREND_MIN_BUCKETS = 3              # buckets with a score before a trend is shown
PERIODS = (7, 30, 90, 180)         # selectable time periods (days)

CHILD_COLUMN = {"country": "state_code", "state": "district_code", "district": "city_code"}
LEVEL_COLUMN = {"state": "state_code", "district": "district_code", "city": "city_code"}

COLUMNS = (
    Measurement.nqi, Measurement.download_mbps, Measurement.upload_mbps, Measurement.latency_ms,
    Measurement.jitter_ms, Measurement.cell_id, Measurement.created_at, Measurement.state_code,
    Measurement.district_code, Measurement.city_code, Measurement.provider_id,
)


# ---------- Filters ----------

@dataclass(frozen=True)
class Filters:
    period_days: int | None = None     # None = the full freshness window
    provider_id: int | None = None
    provider_slug: str | None = None
    unidentified: bool = False         # only tests whose provider couldn't be identified

    @property
    def is_default(self) -> bool:
        return self.period_days is None and self.provider_id is None and not self.unidentified

    def effective_days(self) -> int:
        return self.period_days or current_app.config["FRESHNESS_WINDOW_DAYS"]

    def to_public(self) -> dict:
        return {"period_days": self.effective_days(),
                "provider": "unidentified" if self.unidentified else self.provider_slug}


DEFAULT_FILTERS = Filters()


# ---------- Which measurements count ----------

def base_conditions(filters: Filters = DEFAULT_FILTERS) -> list:
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=filters.effective_days())
    # Genuine user-submitted tests only; flagged (VPN/implausible) results never count.
    conditions = [Measurement.flagged.is_(False), Measurement.created_at >= cutoff,
                  Measurement.source == "user"]
    if filters.provider_id is not None:
        conditions.append(Measurement.provider_id == filters.provider_id)
    if filters.unidentified:
        conditions.append(Measurement.provider_id.is_(None))
    return conditions


def rows_for_region(region: Region, filters: Filters = DEFAULT_FILTERS) -> list:
    query = select(*COLUMNS).where(*base_conditions(filters))
    if region.level != "country":
        query = query.where(getattr(Measurement, LEVEL_COLUMN[region.level]) == region.code)
    return db.session.execute(query).all()


def rows_for_cell(cell: str, filters: Filters = DEFAULT_FILTERS) -> list:
    query = select(*COLUMNS).where(*base_conditions(filters), Measurement.cell_id.like(f"{cell}%"))
    return db.session.execute(query).all()


def rows_in_bbox(south: float, west: float, north: float, east: float,
                 filters: Filters = DEFAULT_FILTERS) -> list:
    query = select(*COLUMNS).where(
        *base_conditions(filters),
        Measurement.cell_lat.between(south, north),
        Measurement.cell_lng.between(west, east),
    )
    return db.session.execute(query).all()


# ---------- Summaries ----------

def iso(dt: datetime | None) -> str | None:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


def requirement(level: str) -> dict:
    return asdict(RULES[level])


def summarize(rows: list, level: str) -> dict:
    rule = RULES[level]
    neighbourhoods = {r.cell_id[:6] for r in rows}
    districts = {r.district_code for r in rows if r.district_code}
    enough = (len(rows) >= rule.min_samples and len(neighbourhoods) >= rule.min_neighbourhoods
              and len(districts) >= rule.min_districts)

    summary = {
        "status": "ok" if enough else ("insufficient" if rows else "no_data"),
        "score": None,
        "band": None,
        "sample_count": len(rows),
        "neighbourhood_count": len(neighbourhoods),
        "block_count": len({r.cell_id for r in rows}),
        "district_count": len(districts),
        "last_updated": iso(max((r.created_at for r in rows), default=None)),
        "medians": None,
        "requirement": requirement(level),
    }
    if enough:
        score = round(median(r.nqi for r in rows))
        summary.update(score=score, band=nqi.band(score), medians={
            "download_mbps": round(median(r.download_mbps for r in rows), 1),
            "upload_mbps": round(median(r.upload_mbps for r in rows), 1),
            "latency_ms": round(median(r.latency_ms for r in rows)),
            "jitter_ms": round(median(r.jitter_ms for r in rows), 1),
        })
    return summary


def children_stats(region: Region, rows: list) -> list[dict]:
    """Every child region (with or without data) and its own summary."""
    column = CHILD_COLUMN.get(region.level)
    if column is None:
        return []
    groups = defaultdict(list)
    for row in rows:
        groups[getattr(row, column)].append(row)
    children = [c for c in region.children]
    if region.level == "district":
        # Cities: list only those with data, biggest first (districts can hold many towns).
        children = sorted((c for c in children if c.code in groups), key=lambda c: -(c.population or 0))
    return [{**child.to_summary(), "bbox": child.bbox(), "summary": summarize(groups.get(child.code, []), child.level)}
            for child in children]


def providers_ranking(rows: list, level: str | None = None) -> dict:
    """Median NQI per provider; a provider is ranked only with PROVIDER_MIN_SAMPLES tests here."""
    groups = defaultdict(list)
    for row in rows:
        groups[row.provider_id].append(row)
    unidentified = len(groups.pop(None, []))
    providers = {p.id: p for p in db.session.scalars(select(Provider).where(Provider.id.in_(groups)))}

    ranked, insufficient = [], []
    for provider_id, group in groups.items():
        entry = {**providers[provider_id].to_summary(), "sample_count": len(group),
                 "last_updated": iso(max(r.created_at for r in group))}
        if len(group) >= PROVIDER_MIN_SAMPLES:
            score = round(median(r.nqi for r in group))
            entry.update(score=score, band=nqi.band(score),
                         download_mbps=round(median(r.download_mbps for r in group), 1),
                         upload_mbps=round(median(r.upload_mbps for r in group), 1),
                         latency_ms=round(median(r.latency_ms for r in group)))
            ranked.append(entry)
        else:
            insufficient.append(entry)
    ranked.sort(key=lambda e: (-e["score"], -e["sample_count"]))
    insufficient.sort(key=lambda e: -e["sample_count"])
    return {"ranked": ranked, "insufficient": insufficient, "min_samples": PROVIDER_MIN_SAMPLES,
            "unidentified_count": unidentified}


def neighbourhoods(rows: list) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        groups[row.cell_id[:6]].append(row)
    return [cell_feature(cell, group, "neighbourhood") for cell, group in groups.items()]


def cell_feature(cell: str, rows: list, level: str) -> dict:
    south, west, north, east = geohash.bounds(cell)
    s = summarize(rows, level)
    return {
        "cell_id": cell,
        "level": level,
        "bounds": [round(v, 6) for v in (south, west, north, east)],
        "center": [round((south + north) / 2, 6), round((west + east) / 2, 6)],
        "status": s["status"], "score": s["score"], "band": s["band"],
        "sample_count": s["sample_count"], "last_updated": s["last_updated"],
    }


def cells_in_bbox(bbox: list[float], precision: int, filters: Filters = DEFAULT_FILTERS) -> list[dict]:
    level = "block" if precision == geohash.BLOCK_PRECISION else "neighbourhood"
    groups = defaultdict(list)
    for row in rows_in_bbox(*bbox, filters=filters):
        groups[row.cell_id[:precision]].append(row)
    return [cell_feature(cell, group, level) for cell, group in groups.items()]


def distribution(areas: list[dict]) -> dict:
    counts = {"good": 0, "fair": 0, "weak": 0, "insufficient": 0}
    for area in areas:
        counts[area["band"] if area["status"] == "ok" else "insufficient"] += 1
    return counts


# ---------- Density and trends ----------

DENSITY_BUCKETS = (("1–4 tests", 1, 4), ("5–19 tests", 5, 19), ("20+ tests", 20, None))


def density(areas: list[dict]) -> dict:
    """How many tests each neighbourhood has (measurement density)."""
    counts = sorted(a["sample_count"] for a in areas)
    return {
        "neighbourhoods": len(counts),
        "median_tests_per_neighbourhood": median(counts) if counts else None,
        "max_tests_per_neighbourhood": counts[-1] if counts else None,
        "buckets": [{"label": label, "count": sum(1 for c in counts if c >= lo and (hi is None or c <= hi))}
                    for label, lo, hi in DENSITY_BUCKETS],
    }


def trend(rows: list, period_days: int) -> dict:
    """Median score per week (periods ≤ 30 days) or per 30 days; buckets need TREND_MIN_SAMPLES."""
    bucket_days = 7 if period_days <= 30 else 30
    count = max(1, math.ceil(period_days / bucket_days))
    end = hour_now() + timedelta(hours=1)
    buckets = []
    for i in range(count - 1, -1, -1):
        b_end = end - timedelta(days=i * bucket_days)
        b_start = b_end - timedelta(days=bucket_days)
        selected = [r for r in rows if b_start <= r.created_at < b_end]
        score = round(median(r.nqi for r in selected)) if len(selected) >= TREND_MIN_SAMPLES else None
        buckets.append({"start": iso(b_start), "end": iso(b_end), "sample_count": len(selected),
                        "score": score, "band": nqi.band(score)})
    scored = sum(1 for b in buckets if b["score"] is not None)
    return {"bucket_days": bucket_days, "buckets": buckets, "enough_data": scored >= TREND_MIN_BUCKETS,
            "min_samples_per_bucket": TREND_MIN_SAMPLES}


def insights(rows: list, level: str, filters: Filters = DEFAULT_FILTERS) -> dict:
    areas = neighbourhoods(rows)
    scored = sorted((a for a in areas if a["status"] == "ok"), key=lambda a: a["score"])
    return {
        "summary": summarize(rows, level),
        "neighbourhood_distribution": distribution(areas),
        "weakest": [a for a in scored if a["band"] != "good"][:5],
        "strongest": list(reversed(scored[-5:])),
        "density": density(areas),
        "trend": trend(rows, filters.effective_days()),
        "providers": providers_ranking(rows),
        "filters": filters.to_public(),
    }


def statistics(rows: list, level: str, filters: Filters = DEFAULT_FILTERS) -> dict:
    """Headline numbers for planners and the home page."""
    areas = neighbourhoods(rows)
    identified = sum(1 for r in rows if r.provider_id is not None)
    ranking = providers_ranking(rows)
    return {
        "summary": summarize(rows, level),
        "neighbourhood_distribution": distribution(areas),
        "coverage": {
            "neighbourhoods_tested": len(areas),
            "neighbourhoods_with_score": sum(1 for a in areas if a["status"] == "ok"),
            "blocks_tested": len({r.cell_id for r in rows}),
            "districts_tested": len({r.district_code for r in rows if r.district_code}),
            "states_tested": len({r.state_code for r in rows if r.state_code}),
        },
        "density": density(areas),
        "providers": {
            "identified_share": round(identified / len(rows), 3) if rows else None,
            "ranked": len(ranking["ranked"]),
        },
        "freshness_window_days": current_app.config["FRESHNESS_WINDOW_DAYS"],
        "filters": filters.to_public(),
    }


# ---------- Guided navigation ----------

WALKING_M_PER_MIN = 80        # ≈ 4.8 km/h
DETOUR_FACTOR = 1.3           # streets are longer than a straight line
DISTANCE_PENALTY_M = 50       # ranking: 1 score point per 50 m of distance
MIN_IMPROVEMENT = 5           # a destination must beat the current area by this many points
MAX_DESTINATIONS = 5


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


def nearby_destinations(origin: str, radius_m: int, filters: Filters = DEFAULT_FILTERS) -> dict:
    """Nearby blocks/neighbourhoods with stronger past connectivity than the origin block.

    Only areas that themselves pass the ≥ 5 test rule and score Good are suggested.
    Distances are from the origin *block's centre* (the server never sees the exact position).
    """
    origin_center = geohash.center(origin)
    d_lat = radius_m / 111_320
    d_lng = radius_m / (111_320 * max(math.cos(math.radians(origin_center[0])), 0.1))
    rows = rows_in_bbox(origin_center[0] - d_lat, origin_center[1] - d_lng,
                        origin_center[0] + d_lat, origin_center[1] + d_lng, filters)

    block_here = summarize([r for r in rows if r.cell_id == origin], "block")
    neighbourhood_here = summarize([r for r in rows if r.cell_id[:6] == origin[:6]], "neighbourhood")
    current = block_here["score"] if block_here["score"] is not None else neighbourhood_here["score"]

    candidates = []
    for level, precision in (("block", 7), ("neighbourhood", 6)):
        groups = defaultdict(list)
        for row in rows:
            groups[row.cell_id[:precision]].append(row)
        for cell, group in groups.items():
            if origin.startswith(cell):
                continue  # that's where the user already is
            feature = cell_feature(cell, group, level)
            if feature["band"] != "good" or (current is not None and feature["score"] < current + MIN_IMPROVEMENT):
                continue
            distance = haversine_m(origin_center, tuple(feature["center"]))
            if distance > radius_m:
                continue
            feature.update(
                distance_m=round(distance),
                walking_minutes_estimate=max(1, round(distance * DETOUR_FACTOR / WALKING_M_PER_MIN)),
                rank=feature["score"] - distance / DISTANCE_PENALTY_M,
            )
            candidates.append(feature)

    # Prefer precise ~150 m blocks; add ~1 km neighbourhoods only where no chosen block lies inside them.
    blocks = sorted((c for c in candidates if c["level"] == "block"), key=lambda c: -c["rank"])[:MAX_DESTINATIONS]
    chosen = list(blocks)
    for n in sorted((c for c in candidates if c["level"] == "neighbourhood"), key=lambda c: -c["rank"]):
        if len(chosen) >= MAX_DESTINATIONS:
            break
        if not any(b["cell_id"].startswith(n["cell_id"]) for b in blocks):
            chosen.append(n)
    chosen.sort(key=lambda c: -c["rank"])
    for c in chosen:
        del c["rank"]

    return {
        "origin": {"cell_id": origin, "current_score": current, "current_band": nqi.band(current),
                   "block": {k: block_here[k] for k in ("status", "score", "sample_count")},
                   "neighbourhood": {k: neighbourhood_here[k] for k in ("status", "score", "sample_count")}},
        "radius_m": radius_m,
        "destinations": chosen,
        "filters": filters.to_public(),
        "notice": "Based on past tests. Connection quality changes over time, so this is a guide, not a guarantee.",
    }
