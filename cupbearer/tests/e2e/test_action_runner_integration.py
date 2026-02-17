from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

import pytest

from conftest import BASE_URL, post_form_raw
from cupbearer.twilio import compute_signature


class _SteersmanHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        token = self.headers.get("X-Steersman-Token")
        if token != "test-steersman-token":
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {
                        "request_id": "r-deny",
                        "audit_ref": "a-deny",
                        "error": {
                            "kind": "auth_denied",
                            "message": "Authentication required",
                            "retryable": False,
                        },
                    }
                ).encode("utf-8")
            )
            return

        if urlparse(self.path).path == "/v1/skills":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {
                        "request_id": "r-skills",
                        "audit_ref": "a-skills",
                        "result": {
                            "skills": [
                                {"name": "reminders", "version": "0.1.0", "enabled": True},
                                {"name": "imessage", "version": "0.1.0", "enabled": True},
                            ]
                        },
                    }
                ).encode("utf-8")
            )
            return

        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(
            json.dumps(
                {
                    "request_id": "r-404",
                    "audit_ref": "a-404",
                    "error": {
                        "kind": "invalid_input",
                        "message": "Unknown endpoint",
                        "retryable": False,
                    },
                }
            ).encode("utf-8")
        )

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        del format
        del args


def _wait_for_live(timeout_seconds: float = 10.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urlopen(f"{BASE_URL}/health/live") as response:
                if response.status == 200:
                    return
        except URLError:
            time.sleep(0.1)
    raise TimeoutError("Timed out waiting for service to become live")


@pytest.mark.e2e
def test_agent_can_call_steersman_skills_tool_and_reply(tmp_path) -> None:
    steersman = HTTPServer(("127.0.0.1", 0), _SteersmanHandler)
    steersman_port = steersman.server_port
    steersman_thread = Thread(target=steersman.serve_forever, daemon=True)
    steersman_thread.start()

    db_path = str(tmp_path / "cupbearer.db")
    env = os.environ.copy()
    env["CUPBEARER_ENV"] = "test"
    env["CUPBEARER_DB_PATH"] = db_path
    env["CUPBEARER_WORKER_POLL_INTERVAL_SECONDS"] = "0.1"
    env["CUPBEARER_WORKER_RETRY_BASE_SECONDS"] = "0.1"
    env["CUPBEARER_WORKER_RETRY_MAX_SECONDS"] = "0.5"
    env["TWILIO_AUTH_TOKEN"] = "test_auth_token"
    env["TWILIO_WHATSAPP_FROM"] = "whatsapp:+14155238886"
    env["CUPBEARER_TWILIO_SEND_MODE"] = "mock"
    env["CUPBEARER_STEERSMAN_BASE_URL"] = f"http://127.0.0.1:{steersman_port}"
    env["CUPBEARER_STEERSMAN_AUTH_TOKEN"] = "test-steersman-token"
    env["CUPBEARER_CLAUDE_MOCK_RESPONSE"] = json.dumps(
        {
            "reply_text": "Checking your available tools.",
            "tool_call": {"name": "steersman.skills.list", "arguments": {}},
        },
        separators=(",", ":"),
    )
    env["CUPBEARER_CLAUDE_MOCK_TOOL_FOLLOWUP_RESPONSE"] = (
        "Available now: reminders and imessage."
    )

    process = subprocess.Popen(
        [
            "python",
            "-m",
            "uvicorn",
            "cupbearer.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8010",
        ],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    captured_logs = ""

    try:
        _wait_for_live()
        path = "/channels/twilio/whatsapp/webhook"
        payload = {
            "MessageSid": "SM_ACTION_1",
            "From": "whatsapp:+15550000009",
            "Body": "What skills do you have right now?",
        }
        signature = compute_signature(
            url=f"{BASE_URL}{path}",
            params=payload,
            auth_token="test_auth_token",
        )
        status, headers, body = post_form_raw(path, payload, headers={"X-Twilio-Signature": signature})
        assert status == 200
        assert headers.get("content-type", "").startswith("text/xml")
        assert "<Response" in body

        with sqlite3.connect(db_path) as connection:
            inbound_row = connection.execute(
                """
                SELECT id FROM events WHERE idempotency_key = ?
                """,
                ("twilio:whatsapp:inbound:SM_ACTION_1",),
            ).fetchone()
        assert inbound_row is not None
        inbound_event_id = inbound_row[0]

        deadline = time.time() + 5
        action_payload = None
        outbound_payload = None
        reaction_payload = None
        while time.time() < deadline:
            with sqlite3.connect(db_path) as connection:
                action_row = connection.execute(
                    """
                    SELECT payload FROM events
                    WHERE idempotency_key = ?
                    """,
                    (f"action:steersman:{inbound_event_id}:steersman.skills.list:0",),
                ).fetchone()
                outbound_row = connection.execute(
                    """
                    SELECT payload FROM events
                    WHERE idempotency_key = ?
                    """,
                    (f"twilio:whatsapp:outbound:reply:{inbound_event_id}",),
                ).fetchone()
                reaction_row = connection.execute(
                    """
                    SELECT payload FROM events
                    WHERE idempotency_key = ?
                    """,
                    (f"twilio:whatsapp:outbound:reaction:tool-success:{inbound_event_id}",),
                ).fetchone()
            if action_row and outbound_row and reaction_row:
                action_payload = json.loads(action_row[0])
                outbound_payload = json.loads(outbound_row[0])
                reaction_payload = json.loads(reaction_row[0])
                break
            time.sleep(0.1)

        assert action_payload is not None
        assert outbound_payload is not None
        assert reaction_payload is not None
        assert action_payload["action_name"] == "steersman.skills.list"
        assert action_payload["ok"] is True
        names = [item["name"] for item in action_payload["response"]["result"]["skills"]]
        assert "reminders" in names
        assert "imessage" in names
        assert reaction_payload["body"] == "✅"
        assert outbound_payload["body"] == "Available now: reminders and imessage."
    finally:
        process.terminate()
        captured_logs, _ = process.communicate(timeout=5)
        steersman.shutdown()
        steersman.server_close()

    assert "turn.start" in captured_logs
    assert "turn.tool.call" in captured_logs
    assert "turn.tool.result" in captured_logs
    assert "turn.tool.followup" in captured_logs
    assert "turn.outbound" in captured_logs
    assert "send.ok" in captured_logs


@pytest.mark.e2e
def test_agent_followup_json_payload_is_not_sent_raw_to_user(tmp_path) -> None:
    steersman = HTTPServer(("127.0.0.1", 0), _SteersmanHandler)
    steersman_port = steersman.server_port
    steersman_thread = Thread(target=steersman.serve_forever, daemon=True)
    steersman_thread.start()

    db_path = str(tmp_path / "cupbearer.db")
    env = os.environ.copy()
    env["CUPBEARER_ENV"] = "test"
    env["CUPBEARER_DB_PATH"] = db_path
    env["CUPBEARER_WORKER_POLL_INTERVAL_SECONDS"] = "0.1"
    env["CUPBEARER_WORKER_RETRY_BASE_SECONDS"] = "0.1"
    env["CUPBEARER_WORKER_RETRY_MAX_SECONDS"] = "0.5"
    env["TWILIO_AUTH_TOKEN"] = "test_auth_token"
    env["TWILIO_WHATSAPP_FROM"] = "whatsapp:+14155238886"
    env["CUPBEARER_TWILIO_SEND_MODE"] = "mock"
    env["CUPBEARER_STEERSMAN_BASE_URL"] = f"http://127.0.0.1:{steersman_port}"
    env["CUPBEARER_STEERSMAN_AUTH_TOKEN"] = "test-steersman-token"
    env["CUPBEARER_CLAUDE_MOCK_RESPONSE"] = json.dumps(
        {
            "reply_text": "Let me check that.",
            "tool_call": {"name": "steersman.skills.list", "arguments": {}},
        },
        separators=(",", ":"),
    )
    env["CUPBEARER_CLAUDE_MOCK_TOOL_FOLLOWUP_RESPONSE"] = (
        '{"request_id":"r-skills","audit_ref":"a-skills","result":{"skills":[{"name":"reminders"}]}}'
    )

    process = subprocess.Popen(
        [
            "python",
            "-m",
            "uvicorn",
            "cupbearer.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8010",
        ],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    try:
        _wait_for_live()
        path = "/channels/twilio/whatsapp/webhook"
        payload = {
            "MessageSid": "SM_ACTION_JSON_1",
            "From": "whatsapp:+15550000010",
            "Body": "show me my skills",
        }
        signature = compute_signature(
            url=f"{BASE_URL}{path}",
            params=payload,
            auth_token="test_auth_token",
        )
        status, headers, body = post_form_raw(path, payload, headers={"X-Twilio-Signature": signature})
        assert status == 200
        assert headers.get("content-type", "").startswith("text/xml")
        assert "<Response" in body

        with sqlite3.connect(db_path) as connection:
            inbound_row = connection.execute(
                """
                SELECT id FROM events WHERE idempotency_key = ?
                """,
                ("twilio:whatsapp:inbound:SM_ACTION_JSON_1",),
            ).fetchone()
        assert inbound_row is not None
        inbound_event_id = inbound_row[0]

        deadline = time.time() + 5
        outbound_payload = None
        while time.time() < deadline:
            with sqlite3.connect(db_path) as connection:
                outbound_row = connection.execute(
                    """
                    SELECT payload FROM events
                    WHERE idempotency_key = ?
                    """,
                    (f"twilio:whatsapp:outbound:reply:{inbound_event_id}",),
                ).fetchone()
            if outbound_row:
                outbound_payload = json.loads(outbound_row[0])
                break
            time.sleep(0.1)

        assert outbound_payload is not None
        assert outbound_payload["body"] == "Done. I ran that action successfully."
    finally:
        process.terminate()
        process.communicate(timeout=5)
        steersman.shutdown()
        steersman.server_close()
