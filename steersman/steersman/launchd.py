import json
import os
import plistlib
import subprocess
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from steersman.config import Settings
from steersman.server import assert_loopback_host


def default_plist_path(label: str) -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"


def _logs_dir() -> Path:
    return Path.home() / ".steersman" / "logs"


def _program_args(settings: Settings) -> list[str]:
    return [
        sys.executable,
        "-m",
        "steersman",
        "serve",
        "--host",
        settings.host,
        "--port",
        str(settings.port),
        "--log-level",
        settings.log_level,
    ]


def build_plist_payload(*, settings: Settings, label: str) -> dict:
    logs_dir = _logs_dir()
    return {
        "Label": label,
        "ProgramArguments": _program_args(settings),
        "RunAtLoad": True,
        "KeepAlive": True,
        "WorkingDirectory": str(Path.cwd()),
        "StandardOutPath": str(logs_dir / f"{label}.out.log"),
        "StandardErrorPath": str(logs_dir / f"{label}.err.log"),
        "EnvironmentVariables": {
            "PATH": os.environ.get("PATH", ""),
            "STEERSMAN_AUTH_TOKEN": settings.auth_token,
            "STEERSMAN_AUDIT_LOG_PATH": settings.audit_log_path,
            "STEERSMAN_IDEMPOTENCY_TTL_SECONDS": str(settings.idempotency_ttl_seconds),
        },
    }


def write_plist(*, path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _logs_dir().mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        plistlib.dump(payload, handle)


def install_launch_agent(
    *,
    settings: Settings,
    label: str,
    plist_path: str | None,
    load: bool,
) -> Path:
    assert_loopback_host(settings.host)
    path = Path(plist_path) if plist_path is not None else default_plist_path(label)
    payload = build_plist_payload(settings=settings, label=label)
    write_plist(path=path, payload=payload)

    if load:
        uid = os.getuid()
        subprocess.run(
            ["launchctl", "bootout", f"gui/{uid}/{label}"],
            capture_output=True,
            text=True,
        )
        bootstrap = subprocess.run(
            ["launchctl", "bootstrap", f"gui/{uid}", str(path)],
            capture_output=True,
            text=True,
        )
        if bootstrap.returncode != 0:
            raise RuntimeError((bootstrap.stderr or bootstrap.stdout).strip() or "launchctl bootstrap failed")
        kickstart = subprocess.run(
            ["launchctl", "kickstart", "-k", f"gui/{uid}/{label}"],
            capture_output=True,
            text=True,
        )
        if kickstart.returncode != 0:
            raise RuntimeError((kickstart.stderr or kickstart.stdout).strip() or "launchctl kickstart failed")

    return path


def _is_loaded(label: str) -> bool:
    uid = os.getuid()
    result = subprocess.run(
        ["launchctl", "print", f"gui/{uid}/{label}"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _health_ok(*, host: str, port: int, timeout_s: float) -> bool:
    url = f"http://{host}:{port}/healthz"
    try:
        with urlopen(url, timeout=timeout_s) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload.get("status") == "ok"
    except (URLError, TimeoutError, json.JSONDecodeError):
        return False


def launch_agent_status(
    *,
    settings: Settings,
    label: str,
    plist_path: str | None,
    timeout_s: float,
) -> dict[str, bool]:
    path = Path(plist_path) if plist_path is not None else default_plist_path(label)
    installed = path.exists()
    loaded = _is_loaded(label)
    health = _health_ok(host=settings.host, port=settings.port, timeout_s=timeout_s)
    return {
        "installed": installed,
        "loaded": loaded,
        "health": health,
    }


def stop_launch_agent(*, label: str, remove_plist: bool, plist_path: str | None) -> None:
    uid = os.getuid()
    subprocess.run(
        ["launchctl", "bootout", f"gui/{uid}/{label}"],
        capture_output=True,
        text=True,
    )
    if remove_plist:
        path = Path(plist_path) if plist_path is not None else default_plist_path(label)
        path.unlink(missing_ok=True)
