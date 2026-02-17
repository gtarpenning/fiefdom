from __future__ import annotations

import subprocess
import time

import pytest

from conftest import get_json, post_json, post_json_error
from cupbearer.db.connection import connect_sqlite
from cupbearer.db.migrations import apply_migrations
from cupbearer.db.repositories import SQLiteJobRepository
from cupbearer.domain.models import Job
from cupbearer.time_utils import utc_now_sqlite
from cupbearer.worker import JobWorker


@pytest.mark.e2e
def test_failing_job_retries_then_dead_letters(running_service: subprocess.Popen) -> None:
    del running_service

    created = post_json(
        "/jobs",
        {
            "type": "test.fail_always",
            "payload": {"value": 1},
            "max_retries": 1,
        },
        headers={"X-Idempotency-Key": "job-idem-1"},
    )
    assert created["deduplicated"] is False

    deadline = time.time() + 5
    latest = {}
    while time.time() < deadline:
        latest = get_json(f"/jobs/{created['job_id']}")
        if latest["status"] == "dead_letter":
            break
        time.sleep(0.1)

    assert latest["status"] == "dead_letter"
    assert latest["retry_count"] == 1
    assert "Intentional failure" in latest["last_error"]


@pytest.mark.e2e
def test_unknown_job_type_is_rejected(running_service: subprocess.Popen) -> None:
    del running_service

    status, body = post_json_error(
        "/jobs",
        {
            "type": "unknown.job",
            "payload": {"value": 1},
        },
        headers={"X-Idempotency-Key": "job-idem-reject-1"},
    )
    assert status == 422
    assert "Unsupported job type" in body["detail"]


@pytest.mark.e2e
def test_worker_can_process_existing_pending_job_after_restart(tmp_path) -> None:
    db_path = tmp_path / "resume.db"
    apply_migrations(str(db_path))

    with connect_sqlite(str(db_path)) as connection:
        jobs = SQLiteJobRepository(connection)
        jobs.enqueue(
            Job(
                id="job_resume_1",
                type="noop",
                payload='{"hello":"world"}',
                status="pending",
                retry_count=0,
                max_retries=1,
                available_at=utc_now_sqlite(),
                idempotency_key="resume-idem-1",
            )
        )

    # Simulate a process restart by creating a fresh worker against persisted DB.
    worker = JobWorker(str(db_path), poll_interval_seconds=0.01, retry_base_seconds=0.01)
    processed = worker.process_one_due_job()
    assert processed is True

    with connect_sqlite(str(db_path)) as connection:
        jobs = SQLiteJobRepository(connection)
        job = jobs.get("job_resume_1")

    assert job is not None
    assert job.status == "succeeded"
