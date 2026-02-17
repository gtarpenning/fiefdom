from __future__ import annotations

import sqlite3

from cupbearer.domain.models import Event, Job
from cupbearer.time_utils import utc_now_sqlite


class SQLiteEventRepository:
    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection

    def append(self, event: Event) -> None:
        self._connection.execute(
            """
            INSERT INTO events (
                id,
                direction,
                source,
                type,
                payload,
                idempotency_key,
                thread_id,
                contact_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                event.id,
                event.direction,
                event.source,
                event.type,
                event.payload,
                event.idempotency_key,
                event.thread_id,
                event.contact_id,
            ),
        )
        self._connection.commit()

    def append_idempotent(self, event: Event) -> tuple[Event, bool]:
        try:
            self.append(event)
            return event, True
        except sqlite3.IntegrityError:
            if event.idempotency_key is None:
                raise
            existing = self.get_by_idempotency_key(event.idempotency_key)
            if existing is None:
                raise
            return existing, False

    def get(self, event_id: str) -> Event | None:
        row = self._connection.execute(
            """
            SELECT
                id,
                direction,
                source,
                type,
                payload,
                idempotency_key,
                thread_id,
                contact_id
            FROM events
            WHERE id = ?;
            """,
            (event_id,),
        ).fetchone()

        if row is None:
            return None

        return Event(
            id=row["id"],
            direction=row["direction"],
            source=row["source"],
            type=row["type"],
            payload=row["payload"],
            idempotency_key=row["idempotency_key"],
            thread_id=row["thread_id"],
            contact_id=row["contact_id"],
        )

    def get_by_idempotency_key(self, idempotency_key: str) -> Event | None:
        row = self._connection.execute(
            """
            SELECT
                id,
                direction,
                source,
                type,
                payload,
                idempotency_key,
                thread_id,
                contact_id
            FROM events
            WHERE idempotency_key = ?;
            """,
            (idempotency_key,),
        ).fetchone()

        if row is None:
            return None

        return Event(
            id=row["id"],
            direction=row["direction"],
            source=row["source"],
            type=row["type"],
            payload=row["payload"],
            idempotency_key=row["idempotency_key"],
            thread_id=row["thread_id"],
            contact_id=row["contact_id"],
        )


class SQLiteJobRepository:
    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection

    def enqueue(self, job: Job) -> tuple[Job, bool]:
        try:
            self._connection.execute(
                """
                INSERT INTO jobs (
                    id,
                    type,
                    payload,
                    status,
                    retry_count,
                    max_retries,
                    available_at,
                    last_error,
                    idempotency_key,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    job.id,
                    job.type,
                    job.payload,
                    job.status,
                    job.retry_count,
                    job.max_retries,
                    job.available_at,
                    job.last_error,
                    job.idempotency_key,
                    utc_now_sqlite(),
                    utc_now_sqlite(),
                ),
            )
            self._connection.commit()
            return job, True
        except sqlite3.IntegrityError:
            if job.idempotency_key is None:
                raise
            existing = self.get_by_idempotency_key(job.idempotency_key)
            if existing is None:
                raise
            return existing, False

    def claim_due(self, now: str) -> Job | None:
        row = self._connection.execute(
            """
            SELECT
                id,
                type,
                payload,
                status,
                retry_count,
                max_retries,
                available_at,
                last_error,
                idempotency_key
            FROM jobs
            WHERE status IN ('pending', 'retry')
              AND available_at <= ?
            ORDER BY available_at ASC
            LIMIT 1;
            """,
            (now,),
        ).fetchone()
        if row is None:
            return None

        result = self._connection.execute(
            """
            UPDATE jobs
            SET status = 'running', updated_at = ?
            WHERE id = ?
              AND status IN ('pending', 'retry');
            """,
            (utc_now_sqlite(), row["id"]),
        )
        self._connection.commit()
        if result.rowcount == 0:
            return None

        return Job(
            id=row["id"],
            type=row["type"],
            payload=row["payload"],
            status="running",
            retry_count=row["retry_count"],
            max_retries=row["max_retries"],
            available_at=row["available_at"],
            last_error=row["last_error"],
            idempotency_key=row["idempotency_key"],
        )

    def mark_succeeded(self, job_id: str) -> None:
        self._connection.execute(
            """
            UPDATE jobs
            SET status = 'succeeded',
                updated_at = ?,
                last_error = NULL
            WHERE id = ?;
            """,
            (utc_now_sqlite(), job_id),
        )
        self._connection.commit()

    def mark_retry(self, job_id: str, retry_count: int, next_available_at: str, error: str) -> None:
        self._connection.execute(
            """
            UPDATE jobs
            SET status = 'retry',
                retry_count = ?,
                available_at = ?,
                last_error = ?,
                updated_at = ?
            WHERE id = ?;
            """,
            (retry_count, next_available_at, error, utc_now_sqlite(), job_id),
        )
        self._connection.commit()

    def mark_dead_letter(self, job_id: str, error: str) -> None:
        self._connection.execute(
            """
            UPDATE jobs
            SET status = 'dead_letter',
                last_error = ?,
                updated_at = ?
            WHERE id = ?;
            """,
            (error, utc_now_sqlite(), job_id),
        )
        self._connection.commit()

    def get(self, job_id: str) -> Job | None:
        row = self._connection.execute(
            """
            SELECT
                id,
                type,
                payload,
                status,
                retry_count,
                max_retries,
                available_at,
                last_error,
                idempotency_key
            FROM jobs
            WHERE id = ?;
            """,
            (job_id,),
        ).fetchone()
        if row is None:
            return None
        return Job(
            id=row["id"],
            type=row["type"],
            payload=row["payload"],
            status=row["status"],
            retry_count=row["retry_count"],
            max_retries=row["max_retries"],
            available_at=row["available_at"],
            last_error=row["last_error"],
            idempotency_key=row["idempotency_key"],
        )

    def get_by_idempotency_key(self, idempotency_key: str) -> Job | None:
        row = self._connection.execute(
            """
            SELECT
                id,
                type,
                payload,
                status,
                retry_count,
                max_retries,
                available_at,
                last_error,
                idempotency_key
            FROM jobs
            WHERE idempotency_key = ?;
            """,
            (idempotency_key,),
        ).fetchone()
        if row is None:
            return None
        return Job(
            id=row["id"],
            type=row["type"],
            payload=row["payload"],
            status=row["status"],
            retry_count=row["retry_count"],
            max_retries=row["max_retries"],
            available_at=row["available_at"],
            last_error=row["last_error"],
            idempotency_key=row["idempotency_key"],
        )
