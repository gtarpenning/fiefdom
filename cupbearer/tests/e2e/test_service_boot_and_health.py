from __future__ import annotations

import os
import subprocess

import pytest

from conftest import get_json


@pytest.mark.e2e
def test_service_boots_and_reports_health(running_service: subprocess.Popen) -> None:
    del running_service

    live_response = get_json("/health/live")
    ready_response = get_json("/health/ready")

    assert live_response == {"status": "ok"}
    assert ready_response == {"status": "ready"}


@pytest.mark.e2e
def test_startup_fails_without_required_env() -> None:
    env = os.environ.copy()
    env.pop("CUPBEARER_ENV", None)

    process = subprocess.Popen(
        [
            "python",
            "-m",
            "uvicorn",
            "cupbearer.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8011",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    stdout, stderr = process.communicate(timeout=10)
    combined = (stdout + stderr).decode("utf-8")

    assert process.returncode != 0
    assert "Missing required environment variable: CUPBEARER_ENV" in combined
