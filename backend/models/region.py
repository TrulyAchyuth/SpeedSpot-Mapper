"""Administrative regions: India → State/UT → District → City.

Neighbourhoods and ~150 m blocks are *not* rows here — they are geohash grid
cells (see docs/GEOSPATIAL.md). Boundary geometry lives in GeoJSON files;
this table only holds identity, hierarchy and lightweight map metadata.
"""
from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db

REGION_LEVELS = ("country", "state", "district", "city")


class Region(db.Model):
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Stable public identifier: "IN", "IN-TN" (ISO 3166-2:IN), "IN-TN-D603" (LGD district),
    # "IN-TN-C1264527" (GeoNames city).
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    level: Mapped[str] = mapped_column(String(16), index=True)
    # e.g. "state" / "union_territory" for level == "state".
    kind: Mapped[str | None] = mapped_column(String(32))
    # Government of India Local Government Directory code (states and districts).
    lgd_code: Mapped[str | None] = mapped_column(String(16))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id"), index=True)
    population: Mapped[int | None] = mapped_column(Integer)  # cities only (GeoNames)

    # Used to fit the map to a region. Cities have no official boundary, so their box is
    # an approximate view area around the centre point.
    min_lat: Mapped[float | None] = mapped_column(Float)
    min_lng: Mapped[float | None] = mapped_column(Float)
    max_lat: Mapped[float | None] = mapped_column(Float)
    max_lng: Mapped[float | None] = mapped_column(Float)
    center_lat: Mapped[float | None] = mapped_column(Float)
    center_lng: Mapped[float | None] = mapped_column(Float)

    parent: Mapped["Region | None"] = relationship(back_populates="children", remote_side=[id])
    children: Mapped[list["Region"]] = relationship(back_populates="parent", order_by="Region.name")

    def bbox(self) -> list[float] | None:
        """[south, west, north, east], or None if unknown."""
        values = [self.min_lat, self.min_lng, self.max_lat, self.max_lng]
        return None if any(v is None for v in values) else values

    def center(self) -> list[float] | None:
        if self.center_lat is not None and self.center_lng is not None:
            return [self.center_lat, self.center_lng]
        box = self.bbox()
        return [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2] if box else None

    def breadcrumb(self) -> list["Region"]:
        chain, node = [], self
        while node is not None:
            chain.append(node)
            node = node.parent
        return list(reversed(chain))

    def label(self) -> str:
        """Human-friendly context, e.g. 'District in Tamil Nadu'."""
        noun = {"country": "Country", "state": "State", "district": "District", "city": "City"}[self.level]
        if self.kind == "union_territory":
            noun = "Union Territory"
        places = [r.name for r in self.breadcrumb()[1:-1]]
        return f"{noun} in {', '.join(reversed(places))}" if places else noun

    def to_summary(self) -> dict:
        return {"code": self.code, "name": self.name, "level": self.level, "kind": self.kind}

    def to_place(self) -> dict:
        """Summary plus what the map needs to show the region."""
        return {**self.to_summary(), "label": self.label(), "bbox": self.bbox(), "center": self.center()}

    def to_detail(self) -> dict:
        return {
            **self.to_place(),
            "lgd_code": self.lgd_code,
            "population": self.population,
            "parent": self.parent.to_summary() if self.parent else None,
            "breadcrumb": [r.to_summary() for r in self.breadcrumb()],
            "children": [c.to_summary() for c in self.children],
        }
