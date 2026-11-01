"""Time helpers."""
from datetime import datetime, timezone


def hour_now() -> datetime:
    """Current UTC time rounded down to the hour (privacy: no exact minute is stored)."""
    return datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0, tzinfo=None)
