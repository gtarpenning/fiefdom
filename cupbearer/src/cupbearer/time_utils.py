from __future__ import annotations

from datetime import UTC, datetime, timedelta


def utc_now_sqlite() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def add_seconds_sqlite(base_time: str, seconds: float) -> str:
    dt = datetime.strptime(base_time, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
    next_dt = dt + timedelta(seconds=seconds)
    return next_dt.strftime("%Y-%m-%d %H:%M:%S")
