"""Find which state, district and city a ~150 m block belongs to.

Uses the same simplified LGD district polygons the map draws (≈90 m tolerance), so a
block within ~100 m of a district border may occasionally land in the neighbour.
Cities have no official polygon: a block belongs to the nearest city whose
approximate view box contains it.
"""
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from .regions import REFERENCE_DIR, city_half_span

DISTRICTS_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "static" / "geo" / "districts"


@dataclass(frozen=True)
class Location:
    state_code: str
    district_code: str
    city_code: str | None


class _Index:
    def __init__(self):
        self.district_codes, district_geoms = [], []
        for path in sorted(DISTRICTS_DIR.glob("*.geojson")):
            for feature in json.loads(path.read_text(encoding="utf-8"))["features"]:
                self.district_codes.append(feature["properties"]["code"])
                district_geoms.append(shape(feature["geometry"]))
        self.district_geoms = district_geoms
        self.district_tree = STRtree(district_geoms)

        cities = json.loads((REFERENCE_DIR / "india_cities.json").read_text(encoding="utf-8"))["cities"]
        self.cities = cities
        self.city_tree = STRtree([Point(c["lng"], c["lat"]) for c in cities])

    def locate(self, lat: float, lng: float) -> Location | None:
        point = Point(lng, lat)
        for i in self.district_tree.query(point):
            if self.district_geoms[i].covers(point):
                district_code = self.district_codes[i]
                break
        else:
            return None
        state_code = district_code.rsplit("-", 1)[0]
        return Location(state_code, district_code, self._city(point))

    def _city(self, point: Point) -> str | None:
        # Biggest view box is 0.22°; look at every city that close, keep the nearest that fits.
        best = None
        for i in self.city_tree.query(point.buffer(0.22)):
            city = self.cities[i]
            half = city_half_span(city["population"])
            d_lat, d_lng = abs(city["lat"] - point.y), abs(city["lng"] - point.x)
            if d_lat <= half and d_lng <= half:
                distance = d_lat ** 2 + d_lng ** 2
                if best is None or distance < best[0]:
                    best = (distance, city["code"])
        return best[1] if best else None


@lru_cache(maxsize=1)
def _index() -> _Index:
    return _Index()


def locate(lat: float, lng: float) -> Location | None:
    """Region codes for a point, or None if it is outside India's districts."""
    return _index().locate(lat, lng)
