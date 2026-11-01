"""One speed test. Deliberately holds no IP address, GPS position or device identifier.

Location is only the ~150 m block (geohash-7) plus that block's centre point, which is
no more precise than the block itself and lets us filter by map area quickly.
The network is recorded as an ASN (which identifies a company, not a person).
"""
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db

# Only genuine, user-submitted tests exist. The column stays so future genuine sources
# (e.g. imported open measurement data) can be added explicitly, never generated data.
SOURCES = ("user",)
CONNECTION_TYPES = ("mobile", "wifi", "wired", "unknown")
# How the provider was determined (see services/providers.py).
PROVIDER_STATUSES = ("identified", "other_isp", "vpn_or_hosting", "unknown")


class Measurement(db.Model):
    __tablename__ = "measurements"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)  # UTC, rounded to the hour

    cell_id: Mapped[str] = mapped_column(ForeignKey("grid_cells.cell_id"), index=True)
    cell_lat: Mapped[float] = mapped_column(Float)
    cell_lng: Mapped[float] = mapped_column(Float)
    state_code: Mapped[str | None] = mapped_column(String(32), index=True)
    district_code: Mapped[str | None] = mapped_column(String(32), index=True)
    city_code: Mapped[str | None] = mapped_column(String(32), index=True)

    download_mbps: Mapped[float] = mapped_column(Float)
    upload_mbps: Mapped[float] = mapped_column(Float)
    latency_ms: Mapped[float] = mapped_column(Float)
    jitter_ms: Mapped[float] = mapped_column(Float)
    nqi: Mapped[float] = mapped_column(Float)  # always calculated on the server

    provider_id: Mapped[int | None] = mapped_column(ForeignKey("providers.id"), index=True)
    provider_status: Mapped[str] = mapped_column(String(16), default="unknown")
    asn: Mapped[int | None] = mapped_column(Integer)
    asn_org: Mapped[str | None] = mapped_column(String(120))  # network operator's name, e.g. "Bharti Airtel Limited"

    connection_type: Mapped[str] = mapped_column(String(16), default="unknown")
    engine: Mapped[str] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(8), index=True, default="user")  # always "user"
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)  # excluded from scores
    flag_reason: Mapped[str | None] = mapped_column(String(32))
    # Random UUID created by the browser for each test, so a retried submission isn't counted twice.
    # It identifies the test, not the person (a new one is made every time).
    submission_id: Mapped[str | None] = mapped_column(String(36), unique=True)

    provider = relationship("Provider")

    __table_args__ = (
        Index("ix_measurements_cell_latlng", "cell_lat", "cell_lng"),
        # The database itself refuses impossible values, even if application code had a bug.
        CheckConstraint("download_mbps > 0 AND download_mbps <= 10000", name="ck_measurements_download"),
        CheckConstraint("upload_mbps > 0 AND upload_mbps <= 10000", name="ck_measurements_upload"),
        CheckConstraint("latency_ms > 0 AND latency_ms <= 10000", name="ck_measurements_latency"),
        CheckConstraint("jitter_ms >= 0 AND jitter_ms <= 10000", name="ck_measurements_jitter"),
        CheckConstraint("nqi >= 0 AND nqi <= 100", name="ck_measurements_nqi"),
        CheckConstraint("source = 'user'", name="ck_measurements_source"),
        CheckConstraint("provider_status IN ('identified', 'other_isp', 'vpn_or_hosting', 'unknown')",
                        name="ck_measurements_provider_status"),
        CheckConstraint("connection_type IN ('mobile', 'wifi', 'wired', 'unknown')", name="ck_measurements_connection"),
    )
