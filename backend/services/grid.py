"""Grid cells: create them on first use and remember which region they belong to."""
from ..extensions import db
from ..models import GridCell
from ..utils import geohash
from ..utils.clock import hour_now
from . import geo_lookup
from .geo_lookup import Location


def _make_cell(cell_id: str) -> GridCell | None:
    south, west, north, east = geohash.bounds(cell_id)
    lat, lng = (south + north) / 2, (west + east) / 2
    location = geo_lookup.locate(lat, lng)
    if location is None:
        return None
    return GridCell(
        cell_id=cell_id, precision=len(cell_id), center_lat=round(lat, 6), center_lng=round(lng, 6),
        min_lat=south, min_lng=west, max_lat=north, max_lng=east,
        state_code=location.state_code, district_code=location.district_code, city_code=location.city_code,
        first_seen_at=hour_now(),
    )


def ensure_block(block_id: str) -> GridCell | None:
    """Return the block (creating it and its neighbourhood if new), or None if outside India."""
    block = db.session.get(GridCell, block_id)
    if block is None:
        block = _make_cell(block_id)
        if block is None:
            return None
        db.session.add(block)
    neighbourhood_id = block_id[:geohash.NEIGHBOURHOOD_PRECISION]
    if db.session.get(GridCell, neighbourhood_id) is None:
        neighbourhood = _make_cell(neighbourhood_id)
        if neighbourhood is not None:
            db.session.add(neighbourhood)
    return block


def location_of(block: GridCell) -> Location:
    return Location(block.state_code, block.district_code, block.city_code)
