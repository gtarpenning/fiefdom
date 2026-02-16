import json
import shutil
import subprocess
from typing import Any

from steersman.errors import AppError


PRIORITY_TO_REMINDCTL = {
    0: "none",
    1: "high",
    2: "high",
    3: "high",
    4: "high",
    5: "medium",
    6: "low",
    7: "low",
    8: "low",
    9: "low",
}

REMINDCTL_TO_PRIORITY = {
    "none": 0,
    "high": 1,
    "medium": 5,
    "low": 9,
}


def _normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    completed = bool(item.get("isCompleted", False))
    return {
        "id": item.get("id", ""),
        "title": item.get("title", ""),
        "list": item.get("listName", ""),
        "due": item.get("dueDate"),
        "notes": item.get("notes"),
        "flagged": False,
        "priority": REMINDCTL_TO_PRIORITY.get(str(item.get("priority", "none")), 0),
        "completed": completed,
        "status": "completed" if completed else "open",
    }


def _extract_json(stdout: str) -> Any:
    text = stdout.strip()
    if not text:
        raise AppError(
            kind="dependency_unavailable",
            message="remindctl returned empty output",
            status_code=503,
            retryable=True,
        )
    for idx, char in enumerate(text):
        if char not in "[{":
            continue
        try:
            return json.loads(text[idx:])
        except json.JSONDecodeError:
            continue
    raise AppError(
        kind="dependency_unavailable",
        message="remindctl returned invalid JSON",
        status_code=503,
        retryable=True,
    )


def _run_remindctl(args: list[str]) -> Any:
    cmd = "remindctl"
    if shutil.which(cmd) is None:
        raise AppError(
            kind="dependency_unavailable",
            message="remindctl binary not found on PATH. Install with: brew install steipete/tap/remindctl",
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
        output = f"{proc.stdout}\n{proc.stderr}".strip() or "remindctl command failed"
        raise AppError(
            kind="dependency_unavailable",
            message=output,
            status_code=503,
            retryable=True,
        )
    return _extract_json(proc.stdout)


def list_remindctl_reminders(
    *,
    list_name: str,
    status: str | None,
) -> list[dict[str, Any]]:
    result = _run_remindctl(["list", list_name])
    if not isinstance(result, list):
        raise AppError(
            kind="dependency_unavailable",
            message="remindctl returned invalid reminder list payload",
            status_code=503,
            retryable=True,
        )
    normalized = [_normalize_item(item) for item in result if isinstance(item, dict)]
    if status is None:
        return normalized
    return [item for item in normalized if item["status"] == status]


def create_remindctl_reminder(
    *,
    list_name: str,
    title: str,
    notes: str | None,
    due: str | None,
    flagged: bool,
    priority: int,
) -> dict[str, Any]:
    if flagged:
        raise AppError(
            kind="invalid_input",
            message="flagged is not supported by remindctl backend yet",
            status_code=400,
            retryable=False,
        )

    lists = _run_remindctl(["list"])
    if not isinstance(lists, list):
        raise AppError(
            kind="dependency_unavailable",
            message="remindctl returned invalid list catalog payload",
            status_code=503,
            retryable=True,
        )
    if not any(isinstance(item, dict) and item.get("title") == list_name for item in lists):
        _run_remindctl(["list", list_name, "--create"])

    args = ["add", "--title", title.strip(), "--list", list_name]
    if notes:
        args.extend(["--notes", notes])
    if due:
        args.extend(["--due", due])
    priority_value = PRIORITY_TO_REMINDCTL.get(priority, "none")
    if priority_value != "none":
        args.extend(["--priority", priority_value])

    result = _run_remindctl(args)
    if not isinstance(result, dict):
        raise AppError(
            kind="dependency_unavailable",
            message="remindctl returned invalid reminder payload",
            status_code=503,
            retryable=True,
        )
    return _normalize_item(result)
