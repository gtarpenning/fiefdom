from __future__ import annotations

import sqlite3
import subprocess

import pytest

from conftest import BASE_URL, post_form_error, post_form_raw, post_json_error
from cupbearer.twilio import compute_signature


@pytest.mark.e2e
def test_twilio_whatsapp_webhook_valid_signature_is_idempotent(
    running_service_twilio: tuple[subprocess.Popen, str],
) -> None:
    process, db_path = running_service_twilio
    del process

    path = "/channels/twilio/whatsapp/webhook"
    payload = {
        "MessageSid": "SM111",
        "From": "whatsapp:+15550000001",
        "Body": "hello from whatsapp",
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
        rows = connection.execute(
            """
            SELECT id FROM events WHERE idempotency_key = ?
            """,
            ("twilio:whatsapp:inbound:SM111",),
        ).fetchall()
    assert len(rows) == 1


@pytest.mark.e2e
def test_twilio_whatsapp_webhook_rejects_invalid_signature(
    running_service_twilio: tuple[subprocess.Popen, str],
) -> None:
    process, db_path = running_service_twilio
    del process
    del db_path

    status, body = post_form_error(
        "/channels/twilio/whatsapp/webhook",
        {
            "MessageSid": "SM222",
            "From": "whatsapp:+15550000002",
            "Body": "hello from whatsapp",
        },
        headers={"X-Twilio-Signature": "bad-signature"},
    )

    assert status == 403
    assert body["detail"] == "Invalid Twilio signature"


@pytest.mark.e2e
def test_whatsapp_send_requires_twilio_sender_configuration(
    running_service: subprocess.Popen,
) -> None:
    del running_service
    status, body = post_json_error(
        "/channels/whatsapp/send",
        {"to": "+15550000003", "body": "hello"},
        headers={"X-Idempotency-Key": "wa-send-config-missing-1"},
    )
    assert status == 503
    assert "Twilio WhatsApp sender is not configured" in body["detail"]
