from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from cupbearer.config import Settings

logger = logging.getLogger(__name__)


class ActionRunnerError(RuntimeError):
    """Raised when executing an outbound action fails."""


@dataclass(frozen=True)
class ActionIntent:
    name: str
    arguments: dict[str, object]


@dataclass(frozen=True)
class ActionResult:
    name: str
    ok: bool
    status_code: int
    response: dict[str, object]


@dataclass(frozen=True)
class AllowedAction:
    method: str
    path_template: str
    mutating: bool


class SteersmanActionRunner:
    """Explicit allowlisted action runner for Steersman /v1 endpoints."""

    _ALLOWED: dict[str, AllowedAction] = {
        "steersman.skills.list": AllowedAction("GET", "/v1/skills", False),
        "steersman.skills.health": AllowedAction("GET", "/v1/skills/{skill}/health", False),
        "steersman.skills.requirements": AllowedAction(
            "GET",
            "/v1/skills/{skill}/requirements",
            False,
        ),
        "steersman.reminders.list": AllowedAction("GET", "/v1/reminders", False),
        "steersman.reminders.create": AllowedAction("POST", "/v1/reminders", True),
        "steersman.imessage.chats": AllowedAction("GET", "/v1/imessage/chats", False),
        "steersman.imessage.send": AllowedAction("POST", "/v1/imessage/send", True),
    }

    def __init__(self, settings: Settings):
        self._settings = settings

    def allowed_action_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._ALLOWED.keys()))

    def run(self, intent: ActionIntent, *, idempotency_key: str) -> ActionResult:
        logger.info("action.start name=%s", intent.name)
        spec = self._ALLOWED.get(intent.name)
        if spec is None:
            allowed = ", ".join(self.allowed_action_names())
            raise ActionRunnerError(f"Action '{intent.name}' is not allowlisted. Allowed: {allowed}")

        path = spec.path_template
        params = dict(intent.arguments)
        if "{skill}" in path:
            skill = params.pop("skill", None)
            if not isinstance(skill, str) or not skill.strip():
                raise ActionRunnerError("Action requires non-empty 'skill' argument")
            path = path.replace("{skill}", skill.strip())

        url = f"{self._settings.steersman_base_url.rstrip('/')}{path}"
        body: bytes | None = None
        headers = {
            "Accept": "application/json",
            "X-Steersman-Token": self._settings.steersman_auth_token,
        }

        if spec.method == "GET":
            query = {
                key: str(value)
                for key, value in params.items()
                if value is not None
            }
            if query:
                url = f"{url}?{urlencode(query)}"
        else:
            headers["Content-Type"] = "application/json"
            headers["Idempotency-Key"] = idempotency_key
            body = json.dumps(params, separators=(",", ":")).encode("utf-8")

        request = Request(url, method=spec.method, data=body, headers=headers)
        logger.info("action.req %s %s", spec.method, path)
        try:
            with urlopen(request, timeout=self._settings.steersman_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
                logger.info("action.ok name=%s status=%d", intent.name, response.status)
                return ActionResult(
                    name=intent.name,
                    ok=True,
                    status_code=response.status,
                    response=payload,
                )
        except HTTPError as err:
            raw = err.read().decode("utf-8")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"error": {"kind": "http_error", "message": raw}}
            logger.warning("action.http_error name=%s status=%d", intent.name, err.code)
            return ActionResult(
                name=intent.name,
                ok=False,
                status_code=err.code,
                response=payload,
            )
        except URLError as err:
            logger.error("action.transport_error name=%s error=%s", intent.name, err)
            raise ActionRunnerError(f"Steersman request failed: {err}") from err
