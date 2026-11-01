"""Grid cells: ~150 m blocks (geohash-7) and ~1 km neighbourhoods (geohash-6).

A row is created the first time a test lands in a cell. It caches the cell's geometry
and which state/district/city it belongs to, so that lookup happens once per cell.
"""
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db


class GridCell(db.Model):
    __tablename__ = "grid_cells"

    cell_id: Mapped[str] = mapped_column(String(7), primary_key=True)
    precision: Mapped[int] = mapped_column(Integer, index=True)  # 7 = block, 6 = neighbourhood
    center_lat: Mapped[float] = mapped_column(Float)
    center_lng: Mapped[float] = mapped_column(Float)
    min_lat: Mapped[float] = mapped_column(Float)
    min_lng: Mapped[float] = mapped_column(Float)
    max_lat: Mapped[float] = mapped_column(Float)
    max_lng: Mapped[float] = mapped_column(Float)
    state_code: Mapped[str | None] = mapped_column(String(32), index=True)
    district_code: Mapped[str | None] = mapped_column(String(32), index=True)
    city_code: Mapped[str | None] = mapped_column(String(32))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime)

    __table_args__ = (CheckConstraint("precision IN (6, 7)", name="ck_grid_cells_precision"),)

    @property
    def level(self) -> str:
        return "block" if self.precision == 7 else "neighbourhood"

    def to_summary(self) -> dict:
        return {
            "cell_id": self.cell_id, "level": self.level,
            "center": [self.center_lat, self.center_lng],
            "bounds": [self.min_lat, self.min_lng, self.max_lat, self.max_lng],
            "state_code": self.state_code, "district_code": self.district_code, "city_code": self.city_code,
        }
