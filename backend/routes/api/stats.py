"""Area statistics. Every score follows the rules in services/stats.py.

All endpoints accept ?period= and ?provider= filters (see areas.parse_filters).
Cached summaries are used only for the default, unfiltered view.
"""
import csv
import io

from flask import Response, request

from ...services import stats, stats_cache
from ...utils import geohash
from ...utils.responses import ApiError, ok
from . import api_v1
from .areas import (cell_level, cell_place, get_region_or_404, parse_filters, region_place, resolve_area,
                    valid_cell_or_400)


def region_children(region, rows, filters):
    if filters.is_default and region.level in stats_cache.CHILD_LEVEL:
        return stats_cache.children_summaries(region)
    return stats.children_stats(region, rows)


@api_v1.get("/regions/<code>/stats")
def region_stats(code: str):
    region = get_region_or_404(code)
    filters = parse_filters()
    rows = stats.rows_for_region(region, filters)
    summary = (stats_cache.region_summary(region, lambda: rows) if filters.is_default
               else stats.summarize(rows, region.level))
    return ok({
        "area": region_place(region),
        "summary": summary,
        "children": region_children(region, rows, filters),
        "providers": stats.providers_ranking(rows),
        "filters": filters.to_public(),
    })


@api_v1.get("/cells/<cell>/stats")
def cell_stats(cell: str):
    cell = valid_cell_or_400(cell)
    filters = parse_filters()
    rows = stats.rows_for_cell(cell, filters)
    level = cell_level(cell)
    return ok({
        "area": cell_place(cell),
        "summary": stats.summarize(rows, level),
        "providers": stats.providers_ranking(rows),
        "filters": filters.to_public(),
    })


def area_rows(default: str | None = None, *, allow_provider: bool = True):
    """(place, rows, level, region-or-None, filters) for the ?area= parameter."""
    filters = parse_filters(allow_provider=allow_provider)
    kind, area = resolve_area(request.args.get("area", default))
    if kind == "region":
        return region_place(area), stats.rows_for_region(area, filters), area.level, area, filters
    return cell_place(area), stats.rows_for_cell(area, filters), cell_level(area), None, filters


@api_v1.get("/insights")
def insights():
    place, rows, level, region, filters = area_rows()
    data = {"area": place, **stats.insights(rows, level, filters)}
    for cell in data["weakest"] + data["strongest"]:
        cell["name"] = cell_place(cell["cell_id"])["name"]
    data["children"] = region_children(region, rows, filters) if region else []
    return ok(data)


@api_v1.get("/statistics")
def statistics():
    """Headline statistics for an area (default: all of India)."""
    place, rows, level, region, filters = area_rows(default="IN")
    data = {"area": place, **stats.statistics(rows, level, filters)}
    if region is not None and region.level in stats_cache.CHILD_LEVEL:
        children = region_children(region, rows, filters)
        data["children_with_score"] = {
            "level": stats_cache.CHILD_LEVEL[region.level],
            "count": sum(1 for c in children if c["summary"]["status"] == "ok"),
            "total": len(children),
        }
    return ok(data)


# ---------- Guided navigation ----------

NAV_DEFAULT_RADIUS_M = 1500
NAV_MAX_RADIUS_M = 3000


@api_v1.get("/navigation/nearby")
def navigation_nearby():
    """Better-connected areas near a ~150 m block. Receives only the block code, never coordinates."""
    cell = (request.args.get("cell") or "").lower()
    if not geohash.is_valid(cell, geohash.BLOCK_PRECISION):
        raise ApiError("invalid_parameter", "That area code isn't valid.", 400,
                       {"cell": "Must be a 7-character area code."})
    try:
        radius = int(request.args.get("radius", NAV_DEFAULT_RADIUS_M))
    except ValueError:
        radius = -1
    if not 200 <= radius <= NAV_MAX_RADIUS_M:
        raise ApiError("invalid_parameter", "Search distance is out of range.", 400,
                       {"radius": f"Must be between 200 and {NAV_MAX_RADIUS_M} metres."})
    return ok(stats.nearby_destinations(cell, radius, parse_filters()))


# ---------- CSV export (aggregated only — never individual tests) ----------

CSV_COLUMNS = ["area_code", "area_name", "area_level", "status", "score", "band", "sample_count",
               "neighbourhood_count", "median_download_mbps", "median_upload_mbps", "median_latency_ms",
               "median_jitter_ms", "last_test"]


def _csv_row(code, name, level, summary):
    medians = summary["medians"] or {}
    return [code, name, level, summary["status"], summary["score"], summary["band"], summary["sample_count"],
            summary["neighbourhood_count"], medians.get("download_mbps"), medians.get("upload_mbps"),
            medians.get("latency_ms"), medians.get("jitter_ms"), summary["last_updated"]]


@api_v1.get("/export/areas.csv")
def export_areas():
    """?area=<region>&type=children|neighbourhoods → one row per sub-area (aggregates only)."""
    export_type = request.args.get("type", "children")
    if export_type not in ("children", "neighbourhoods"):
        raise ApiError("invalid_parameter", "Unknown export type.", 400,
                       {"type": "Must be 'children' or 'neighbourhoods'."})
    filters = parse_filters()
    region = get_region_or_404(request.args.get("area", "IN"))
    rows = stats.rows_for_region(region, filters)

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(CSV_COLUMNS)
    writer.writerow(_csv_row(region.code, region.name, region.level, stats.summarize(rows, region.level)))
    if export_type == "children":
        for child in region_children(region, rows, filters):
            writer.writerow(_csv_row(child["code"], child["name"], child["level"], child["summary"]))
    else:
        groups = {}
        for row in rows:
            groups.setdefault(row.cell_id[:6], []).append(row)
        for cell in sorted(groups):
            writer.writerow(_csv_row(cell, f"Neighbourhood {cell}", "neighbourhood",
                                     stats.summarize(groups[cell], "neighbourhood")))

    period = filters.effective_days()
    filename = f"speedspot-{region.code.lower()}-{export_type}-{period}d.csv"
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})
