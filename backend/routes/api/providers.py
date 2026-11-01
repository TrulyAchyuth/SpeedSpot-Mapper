"""Providers: the list, rankings in an area, and "which provider am I on?"."""
from sqlalchemy import func, select

from ...extensions import db
from ...models import Measurement, Provider
from ...services import providers, stats
from ...utils.client_ip import client_ip
from ...utils.responses import ok
from . import api_v1
from .stats import area_rows


@api_v1.get("/providers")
def list_providers():
    counts = dict(db.session.execute(
        select(Measurement.provider_id, func.count()).where(*stats.base_conditions())
        .group_by(Measurement.provider_id)).all())
    items = [{**p.to_summary(), "asn_count": len(p.asns), "sample_count": counts.get(p.id, 0)}
             for p in db.session.scalars(select(Provider).order_by(Provider.name))]
    return ok(items, meta={"count": len(items)})


@api_v1.get("/providers/rankings")
def provider_rankings():
    # Comparing providers, so only the time filter applies.
    place, rows, level, _, filters = area_rows(default="IN", allow_provider=False)
    return ok({"area": place, "summary": stats.summarize(rows, level),
               "providers": stats.providers_ranking(rows), "filters": filters.to_public()})


@api_v1.get("/me/provider")
def my_provider():
    """Identify the visitor's provider. The IP address is used in memory only and never stored."""
    data = providers.identify(client_ip()).to_public()
    data["lookup_available"] = providers.get_asn_database().available
    return ok(data)
