"""Loading the administrative-region reference data into the database.

Sources (all committed under backend/reference/):
  india_states_uts.json        India + 28 states + 8 UTs (ISO 3166-2:IN, LGD codes)
  india_boundaries_index.json  state bounding boxes + 785 LGD districts (generated)
  india_cities.json            GeoNames cities with 15,000+ people (generated)
  providers.json               major Indian providers
"""
import json
from pathlib import Path

from sqlalchemy import select

from ..extensions import db
from ..models import Provider, ProviderASN, Region

REFERENCE_DIR = Path(__file__).resolve().parent.parent / "reference"
REFERENCE_FILE = REFERENCE_DIR / "india_states_uts.json"


def load_reference(path: Path = REFERENCE_FILE) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def city_half_span(population: int) -> float:
    """Half-width (degrees) of the approximate view box around a city centre."""
    if population >= 5_000_000:
        return 0.22
    if population >= 1_000_000:
        return 0.12
    if population >= 300_000:
        return 0.07
    return 0.04


def _set_bbox(region: Region, bbox: list[float] | None) -> None:
    if bbox:
        region.min_lat, region.min_lng, region.max_lat, region.max_lng = bbox


def seed_reference_regions() -> dict:
    """Insert or update India, states/UTs, districts and cities. Safe to run repeatedly."""
    states_ref = load_reference()
    index = load_reference(REFERENCE_DIR / "india_boundaries_index.json")
    cities = load_reference(REFERENCE_DIR / "india_cities.json")["cities"]

    existing = {r.code: r for r in db.session.scalars(select(Region))}
    created = 0

    def upsert(code: str, **fields) -> Region:
        nonlocal created
        region = existing.get(code)
        if region is None:
            region = existing[code] = Region(code=code)
            db.session.add(region)
            created += 1
        for key, value in fields.items():
            setattr(region, key, value)
        return region

    country = upsert(states_ref["country"]["code"], name=states_ref["country"]["name"],
                     level="country", kind="country")
    country.min_lat, country.min_lng, country.max_lat, country.max_lng = 6.5, 68.0, 37.5, 97.5
    db.session.flush()

    for item in states_ref["states"]:
        state = upsert(item["code"], name=item["name"], level="state", kind=item["kind"],
                       lgd_code=item.get("lgd_code"), parent_id=country.id)
        _set_bbox(state, index["states"].get(item["code"]))
    db.session.flush()

    for item in index["districts"]:
        district = upsert(item["code"], name=item["name"], level="district", kind="district",
                          lgd_code=item["lgd_code"], parent_id=existing[item["state_code"]].id)
        _set_bbox(district, item["bbox"])
    db.session.flush()

    for item in cities:
        half = city_half_span(item["population"])
        city = upsert(item["code"], name=item["name"], level="city", kind="city",
                      population=item["population"], center_lat=item["lat"], center_lng=item["lng"],
                      parent_id=existing[item["district_code"]].id)
        _set_bbox(city, [item["lat"] - half, item["lng"] - half, item["lat"] + half, item["lng"] + half])

    db.session.commit()
    return {"created": created, "total": len(existing)}


def seed_providers() -> int:
    """Insert or update providers and their ASNs from providers.json (idempotent)."""
    data = load_reference(REFERENCE_DIR / "providers.json")["providers"]
    existing = {p.slug: p for p in db.session.scalars(select(Provider))}
    for item in data:
        provider = existing.get(item["slug"]) or Provider(slug=item["slug"])
        provider.name, provider.kind = item["name"], item["kind"]
        db.session.add(provider)
        current = {link.asn: link for link in provider.asns}
        for asn in item["asns"]:
            if asn not in current:
                provider.asns.append(db.session.get(ProviderASN, asn) or ProviderASN(asn=asn))
        for asn, link in current.items():
            if asn not in item["asns"]:
                provider.asns.remove(link)
    db.session.commit()
    return len(data)


def get_region(code: str) -> Region | None:
    return db.session.scalar(select(Region).where(Region.code == code.upper()))
