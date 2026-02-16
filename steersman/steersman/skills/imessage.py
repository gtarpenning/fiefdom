import json
import shutil
import subprocess
from typing import Any

from steersman.errors import AppError


def _run_imsg(args: list[str]) -> list[dict[str, Any]]:
    cmd = "imsg"
    if shutil.which(cmd) is None:
        raise AppError(
            kind="dependency_unavailable",
            message="imsg binary not found on PATH",
            status_code=503,
            retryable=False,
        )

    proc = subprocess.run(
        [cmd, *args, "--json"],
        capture_output=True,
        text=True,
        timeout=20,
    )
    if proc.returncode != 0:
        output = f"{proc.stdout}\n{proc.stderr}".strip() or "imsg command failed"
        raise AppError(
            kind="dependency_unavailable",
            message=output,
            status_code=503,
            retryable=True,
        )

    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    items: list[dict[str, Any]] = []
    for line in lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AppError(
                kind="dependency_unavailable",
                message="imsg returned invalid JSON output",
                status_code=503,
                retryable=True,
            ) from exc
        if isinstance(payload, dict):
            items.append(payload)
        elif isinstance(payload, list):
            items.extend([item for item in payload if isinstance(item, dict)])
    return items


def list_imsg_chats(*, limit: int) -> list[dict[str, Any]]:
    rows = _run_imsg(["chats", "--limit", str(limit)])
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "id": row.get("id"),
                "name": row.get("name"),
                "identifier": row.get("identifier"),
                "service": row.get("service"),
                "last_message_at": row.get("last_message_at"),
            }
        )
    return out


def send_imsg_message(
    *,
    to: str,
    text: str,
    service: str,
) -> dict[str, Any]:
    rows = _run_imsg(["send", "--to", to, "--text", text, "--service", service])
    if not rows:
        return {"status": "sent"}
    status = rows[0].get("status")
    return {"status": status if isinstance(status, str) else "sent"}
