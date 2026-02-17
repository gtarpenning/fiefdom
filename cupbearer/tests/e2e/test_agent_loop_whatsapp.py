from __future__ import annotations

import json
import sqlite3
import subprocess
import time

import pytest

from conftest import BASE_URL, post_form_raw
from cupbearer.twilio import compute_signature


@pytest.mark.e2e
def test_whatsapp_webhook_triggers_agent_reply_once_for_duplicate_delivery(
    running_service_agent: tuple[subprocess.Popen, str],
) -> None:
    process, db_path = running_service_agent
    del process

    path = "/channels/twilio/whatsapp/webhook"
    payload = {
        "MessageSid": "SM_AGENT_1",
        "From": "whatsapp:+15550000008",
        "Body": "plan my week",
    }
    signature = compute_signature(
        url=f"{BASE_URL}{path}",
        params=payload,
        auth_token="test_auth_token",
    )

    first_status, first_headers, first_body = post_form_raw(
        path,
        payload,
        headers={"X-Twilio-Signature": signature},
    )
    second_status, second_headers, second_body = post_form_raw(
        path,
        payload,
        headers={"X-Twilio-Signature": signature},
    )
    assert first_status == 200
    assert second_status == 200
    assert first_headers.get("content-type", "").startswith("text/xml")
    assert second_headers.get("content-type", "").startswith("text/xml")
    assert "<Response" in first_body
    assert "<Response" in second_body

    with sqlite3.connect(db_path) as connection:
        inbound_row = connection.execute(
            """
            SELECT id FROM events WHERE idempotency_key = ?
            """,
            ("twilio:whatsapp:inbound:SM_AGENT_1",),
        ).fetchone()
    assert inbound_row is not None
    inbound_event_id = inbound_row[0]

    deadline = time.time() + 5
    outbound = None
    policy = None
    while time.time() < deadline:
        with sqlite3.connect(db_path) as connection:
            outbound_row = connection.execute(
                """
                SELECT payload FROM events
                WHERE idempotency_key = ?
                """,
                (f"twilio:whatsapp:outbound:reply:{inbound_event_id}",),
            ).fetchone()
            policy_row = connection.execute(
                """
                SELECT payload FROM events
                WHERE idempotency_key = ?
                """,
                (f"policy:outbound:{inbound_event_id}",),
            ).fetchone()
        if outbound_row and policy_row:
            outbound = json.loads(outbound_row[0])
            policy = json.loads(policy_row[0])
            break
        time.sleep(0.1)

    assert outbound is not None
    assert policy is not None
    assert outbound["body"] == "copy that - agent loop is live"
    assert policy["allowed"] is True
    assert policy["reason_code"] == "pass"
