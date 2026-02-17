from __future__ import annotations

import json
import os
import subprocess
import time
from collections.abc import Generator
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest

BASE_URL = "http://127.0.0.1:8010"


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


@pytest.fixture
def running_service(tmp_path) -> Generator[subprocess.Popen, None, None]:
    env = os.environ.copy()
    env["CUPBEARER_ENV"] = "test"
    env["CUPBEARER_DB_PATH"] = str(tmp_path / "cupbearer.db")
    env["CUPBEARER_WORKER_POLL_INTERVAL_SECONDS"] = "0.1"
    env["CUPBEARER_WORKER_RETRY_BASE_SECONDS"] = "0.1"
    env["CUPBEARER_WORKER_RETRY_MAX_SECONDS"] = "0.5"
    env["CUPBEARER_TWILIO_SEND_MODE"] = "live"
    env["TWILIO_ACCOUNT_SID"] = ""
    env["TWILIO_AUTH_TOKEN"] = ""
    env["TWILIO_WHATSAPP_FROM"] = ""

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
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        _wait_for_live()
        yield process
    finally:
        process.terminate()
        process.wait(timeout=5)


@pytest.fixture
def running_service_twilio(tmp_path) -> Generator[tuple[subprocess.Popen, str], None, None]:
    env = os.environ.copy()
    env["CUPBEARER_ENV"] = "test"
    env["CUPBEARER_DB_PATH"] = str(tmp_path / "cupbearer.db")
    env["CUPBEARER_WORKER_POLL_INTERVAL_SECONDS"] = "0.1"
    env["CUPBEARER_WORKER_RETRY_BASE_SECONDS"] = "0.1"
    env["CUPBEARER_WORKER_RETRY_MAX_SECONDS"] = "0.5"
    env["TWILIO_AUTH_TOKEN"] = "test_auth_token"
    env["CUPBEARER_TWILIO_SEND_MODE"] = "mock"
    env["CUPBEARER_CLAUDE_MOCK_RESPONSE"] = "test reply"

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
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        _wait_for_live()
        yield process, env["CUPBEARER_DB_PATH"]
    finally:
        process.terminate()
        process.wait(timeout=5)


@pytest.fixture
def running_service_agent(tmp_path) -> Generator[tuple[subprocess.Popen, str], None, None]:
    env = os.environ.copy()
    db_path = str(tmp_path / "cupbearer.db")
    env["CUPBEARER_ENV"] = "test"
    env["CUPBEARER_DB_PATH"] = db_path
    env["CUPBEARER_WORKER_POLL_INTERVAL_SECONDS"] = "0.1"
    env["CUPBEARER_WORKER_RETRY_BASE_SECONDS"] = "0.1"
    env["CUPBEARER_WORKER_RETRY_MAX_SECONDS"] = "0.5"
    env["TWILIO_AUTH_TOKEN"] = "test_auth_token"
    env["CUPBEARER_TWILIO_SEND_MODE"] = "mock"
    env["TWILIO_WHATSAPP_FROM"] = "whatsapp:+14155238886"
    env["CUPBEARER_CLAUDE_MOCK_RESPONSE"] = "copy that - agent loop is live"

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
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        _wait_for_live()
        yield process, db_path
    finally:
        process.terminate()
        process.wait(timeout=5)


def post_json(path: str, payload: dict, headers: dict[str, str] | None = None) -> dict:
    raw = json.dumps(payload).encode("utf-8")
    request = Request(
        f"{BASE_URL}{path}",
        method="POST",
        data=raw,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def get_json(path: str) -> dict:
    with urlopen(f"{BASE_URL}{path}") as response:
        return json.loads(response.read().decode("utf-8"))


def post_json_error(
    path: str, payload: dict, headers: dict[str, str] | None = None
) -> tuple[int, dict]:
    raw = json.dumps(payload).encode("utf-8")
    request = Request(
        f"{BASE_URL}{path}",
        method="POST",
        data=raw,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urlopen(request):
            pass
    except HTTPError as err:
        body = json.loads(err.read().decode("utf-8"))
        return err.code, body
    raise AssertionError("Expected HTTP error response")


def post_form(path: str, payload: dict[str, str], headers: dict[str, str] | None = None) -> dict:
    raw = urlencode(payload).encode("utf-8")
    request = Request(
        f"{BASE_URL}{path}",
        method="POST",
        data=raw,
        headers={"Content-Type": "application/x-www-form-urlencoded", **(headers or {})},
    )
    with urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def post_form_raw(
    path: str, payload: dict[str, str], headers: dict[str, str] | None = None
) -> tuple[int, dict[str, str], str]:
    raw = urlencode(payload).encode("utf-8")
    request = Request(
        f"{BASE_URL}{path}",
        method="POST",
        data=raw,
        headers={"Content-Type": "application/x-www-form-urlencoded", **(headers or {})},
    )
    with urlopen(request) as response:
        return response.status, dict(response.headers.items()), response.read().decode("utf-8")


def post_form_error(
    path: str, payload: dict[str, str], headers: dict[str, str] | None = None
) -> tuple[int, dict]:
    raw = urlencode(payload).encode("utf-8")
    request = Request(
        f"{BASE_URL}{path}",
        method="POST",
        data=raw,
        headers={"Content-Type": "application/x-www-form-urlencoded", **(headers or {})},
    )
    try:
        with urlopen(request):
            pass
    except HTTPError as err:
        body = json.loads(err.read().decode("utf-8"))
        return err.code, body
    raise AssertionError("Expected HTTP error response")
