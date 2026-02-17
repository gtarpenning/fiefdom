from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    id: str
    direction: str
    source: str
    type: str
    payload: str
    idempotency_key: str | None = None
    thread_id: str | None = None
    contact_id: str | None = None


@dataclass(frozen=True)
class Job:
    id: str
    type: str
    payload: str
    status: str
    retry_count: int
    max_retries: int
    available_at: str
    last_error: str | None = None
    idempotency_key: str | None = None
