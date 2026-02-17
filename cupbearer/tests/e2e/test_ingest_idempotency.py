from __future__ import annotations

import subprocess

import pytest

from conftest import post_json


@pytest.mark.e2e
def test_ingest_event_is_idempotent(running_service: subprocess.Popen) -> None:
    del running_service

    payload = {
        "source": "twilio",
        "type": "message.received",
        "payload": {"text": "hello"},
    }

    first = post_json(
        "/ingest/events",
        payload,
        headers={"X-Idempotency-Key": "ingest-idem-1"},
    )
    second = post_json(
        "/ingest/events",
        payload,
        headers={"X-Idempotency-Key": "ingest-idem-1"},
    )

    assert first["deduplicated"] is False
    assert second["deduplicated"] is True
    assert first["event_id"] == second["event_id"]
