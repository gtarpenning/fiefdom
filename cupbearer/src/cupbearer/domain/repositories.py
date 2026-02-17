from __future__ import annotations

from typing import Protocol

from cupbearer.domain.models import Event, Job


class EventRepository(Protocol):
    def append(self, event: Event) -> None:
        """Append a new immutable event."""

    def get(self, event_id: str) -> Event | None:
        """Fetch one event by ID."""


class JobRepository(Protocol):
    def enqueue(self, job: Job) -> tuple[Job, bool]:
        """Enqueue job and return (job, created)."""

    def claim_due(self, now: str) -> Job | None:
        """Claim one due job for processing."""

    def get(self, job_id: str) -> Job | None:
        """Fetch one job by ID."""
