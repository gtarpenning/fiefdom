from __future__ import annotations

import asyncio
import inspect
import json
import logging
from collections.abc import Callable

from cupbearer.db.connection import connect_sqlite
from cupbearer.db.repositories import SQLiteJobRepository
from cupbearer.domain.models import Job
from cupbearer.time_utils import add_seconds_sqlite, utc_now_sqlite

logger = logging.getLogger(__name__)

JobHandler = Callable[[Job], None]


class JobWorker:
    def __init__(
        self,
        db_path: str,
        poll_interval_seconds: float = 1.0,
        retry_base_seconds: float = 5.0,
        retry_max_seconds: float = 300.0,
    ):
        self._db_path = db_path
        self._poll_interval_seconds = poll_interval_seconds
        self._retry_base_seconds = retry_base_seconds
        self._retry_max_seconds = retry_max_seconds
        self._stop_event = asyncio.Event()
        # Keep handler registration explicit and local for v1 maintainability.
        self._handlers: dict[str, JobHandler] = {
            "noop": self._handle_noop,
            "test.fail_always": self._handle_fail_always,
        }

    def register_handler(self, job_type: str, handler: JobHandler) -> None:
        if inspect.iscoroutinefunction(handler):
            raise TypeError("Job handlers must be synchronous callables.")
        self._handlers[job_type] = handler

    def has_handler(self, job_type: str) -> bool:
        return job_type in self._handlers

    def supported_job_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers.keys()))

    async def run_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                processed = self.process_one_due_job()
            except Exception:  # noqa: BLE001
                if self._stop_event.is_set():
                    break
                raise
            if not processed:
                await asyncio.sleep(self._poll_interval_seconds)

    def stop(self) -> None:
        self._stop_event.set()

    def process_one_due_job(self) -> bool:
        now = utc_now_sqlite()
        with connect_sqlite(self._db_path) as connection:
            jobs = SQLiteJobRepository(connection)
            job = jobs.claim_due(now)
            if job is None:
                return False

            try:
                handler = self._handlers.get(job.type)
                if handler is None:
                    raise RuntimeError(f"No handler registered for job type: {job.type}")

                handler(job)
                jobs.mark_succeeded(job.id)
                logger.info("job.ok %s type=%s", job.id[:8], job.type)
            except Exception as exc:  # noqa: BLE001
                next_retry_count = job.retry_count + 1
                if next_retry_count > job.max_retries:
                    jobs.mark_dead_letter(job.id, str(exc))
                    logger.error("job.dead_letter %s error=%s", job.id[:8], exc)
                else:
                    delay = min(
                        self._retry_max_seconds,
                        self._retry_base_seconds * (2**job.retry_count),
                    )
                    retry_at = add_seconds_sqlite(now, delay)
                    jobs.mark_retry(job.id, next_retry_count, retry_at, str(exc))
                    logger.warning("job.retry %s retry=%d at=%s", job.id[:8], next_retry_count, retry_at)

        return True

    @staticmethod
    def _handle_noop(job: Job) -> None:
        json.loads(job.payload)

    @staticmethod
    def _handle_fail_always(job: Job) -> None:
        del job
        raise RuntimeError("Intentional failure for retry/dead-letter testing")
