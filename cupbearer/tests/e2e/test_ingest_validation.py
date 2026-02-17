from __future__ import annotations

import subprocess

import pytest

from conftest import post_json_error


@pytest.mark.e2e
def test_invalid_event_direction_is_rejected(running_service: subprocess.Popen) -> None:
    del running_service

    status, body = post_json_error(
        "/ingest/events",
        {
            "source": "twilio",
            "type": "message.received",
            "direction": "sideways",
            "payload": {"text": "hello"},
        },
        headers={"X-Idempotency-Key": "ingest-invalid-direction-1"},
    )

    assert status == 422
    assert body["detail"]
