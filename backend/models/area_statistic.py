"""Cached aggregate statistics for one area (India, a state, district, city, neighbourhood or block).

This is a cache, never the source of truth: every row can be rebuilt from `measurements`.
Rows are deleted when a new test lands in the area and expire after STATS_CACHE_TTL_MINUTES
(so tests that age out of the freshness window stop counting).
"""
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db


class AreaStatistic(db.Model):
    __tablename__ = "area_statistics"

    id: Mapped[int] = mapped_column(primary_key=True)
    area_level: Mapped[str] = mapped_column(String(16))
    area_code: Mapped[str] = mapped_column(String(32), index=True)

    status: Mapped[str] = mapped_column(String(16))  # ok / insufficient / no_data
    score: Mapped[int | None] = mapped_column(Integer)
    band: Mapped[str | None] = mapped_column(String(8))
    sample_count: Mapped[int] = mapped_column(Integer)
    neighbourhood_count: Mapped[int] = mapped_column(Integer)
    block_count: Mapped[int] = mapped_column(Integer)
    district_count: Mapped[int] = mapped_column(Integer)
    median_download_mbps: Mapped[float | None] = mapped_column(Float)
    median_upload_mbps: Mapped[float | None] = mapped_column(Float)
    median_latency_ms: Mapped[float | None] = mapped_column(Float)
    median_jitter_ms: Mapped[float | None] = mapped_column(Float)
    last_measurement_at: Mapped[datetime | None] = mapped_column(DateTime)
    computed_at: Mapped[datetime] = mapped_column(DateTime)

    __table_args__ = (UniqueConstraint("area_level", "area_code", name="uq_area_statistic"),)
