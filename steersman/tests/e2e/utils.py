import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.request import Request
from urllib.request import urlopen


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_http(url: str, timeout_s: float = 8.0) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=0.5) as response:
                body = response.read().decode("utf-8")
                return json.loads(body)
        except (URLError, TimeoutError, json.JSONDecodeError):
            time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for {url}")


def request_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: dict | None = None,
    timeout_s: float = 2.0,
) -> tuple[int, dict]:
    data = None
    request_headers = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    request = Request(url=url, method=method, headers=request_headers, data=data)
    try:
        with urlopen(request, timeout=timeout_s) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return int(response.status), payload
    except HTTPError as exc:
        payload = json.loads(exc.read().decode("utf-8"))
        return int(exc.code), payload


def wait_for_jsonl(path: str, timeout_s: float = 2.0) -> list[dict]:
    deadline = time.time() + timeout_s
    file_path = Path(path)
    while time.time() < deadline:
        if file_path.exists():
            with file_path.open("r", encoding="utf-8") as handle:
                events = [json.loads(line) for line in handle if line.strip()]
            if events:
                return events
        time.sleep(0.05)
    return []


@contextmanager
def run_server(env: dict[str, str] | None = None, *, use_fake_bins: bool = True):
    port = free_port()
    with tempfile.TemporaryDirectory() as temp_dir:
        base_env = {**os.environ, **(env or {})}
        if use_fake_bins:
            fake_bin = str((Path(__file__).parent / "fake_bin").resolve())
            base_env["PATH"] = f"{fake_bin}:{base_env.get('PATH', '')}"
            base_env["FAKE_STEERSMAN_STATE_DIR"] = temp_dir

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
            env=base_env,
        )
        base_url = f"http://127.0.0.1:{port}"
        try:
            wait_for_http(f"{base_url}/healthz")
            yield base_url
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
