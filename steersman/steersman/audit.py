import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import Request

from steersman.errors import AppError


def _state_str(request: Request, name: str, default: str) -> str:
    value = getattr(request.state, name, None)
    return value if isinstance(value, str) else default


def emit(
    request: Request,
    *,
    action: str,
    capability: str,
    outcome: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    settings = request.app.state.settings
    event = {
        "ts": datetime.now(UTC).isoformat(),
        "request_id": _state_str(request, "request_id", ""),
        "audit_ref": _state_str(request, "audit_ref", ""),
        "principal": _state_str(request, "principal", "anonymous"),
        "action": action,
        "capability": capability,
        "outcome": outcome,
        "metadata": metadata or {},
    }

    path = Path(settings.audit_log_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, separators=(",", ":")) + "\n")
    except OSError as exc:
        raise AppError(
            kind="dependency_unavailable",
            message=f"Audit sink unavailable: {exc}",
            status_code=503,
            retryable=True,
        ) from exc
