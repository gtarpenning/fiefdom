import json
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_http(url: str, timeout_s: float = 8.0) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=0.5) as response:
                body = response.read().decode("utf-8")
                return json.loads(body)
        except (URLError, TimeoutError, json.JSONDecodeError):
            time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for {url}")


def test_healthz_e2e() -> None:
    port = _free_port()
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "steersman",
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        payload = _wait_for_http(f"http://127.0.0.1:{port}/healthz")
        assert payload == {"status": "ok"}
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_refuses_non_loopback_bind_e2e() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "steersman",
            "serve",
            "--host",
            "0.0.0.0",
            "--port",
            "8765",
        ],
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}"
    assert "Refusing non-loopback bind host" in combined
