import secrets
import time
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from steersman import policy
from steersman.config import Settings
from steersman.errors import AppError
from steersman.models import ActionEnvelope, ErrorPayload


def request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) else uuid4().hex


def audit_ref(request: Request) -> str:
    value = getattr(request.state, "audit_ref", None)
    return value if isinstance(value, str) else f"audit-{uuid4().hex}"


def state_str(request: Request, name: str, default: str) -> str:
    value = getattr(request.state, name, None)
    return value if isinstance(value, str) else default


def error_envelope(
    request: Request,
    *,
    kind: str,
    message: str,
    retryable: bool,
) -> dict:
    return ActionEnvelope(
        request_id=request_id(request),
        audit_ref=audit_ref(request),
        error=ErrorPayload(kind=kind, message=message, retryable=retryable),
    ).model_dump()


def result_envelope(request: Request, result: object) -> dict:
    return ActionEnvelope(
        request_id=request_id(request),
        audit_ref=audit_ref(request),
        result=result,
    ).model_dump()


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def idempotency_tuple(request: Request) -> tuple[str, str, str]:
    key = request.headers.get("Idempotency-Key")
    if key is None or not key.strip():
        raise AppError(
            kind="invalid_input",
            message="Idempotency-Key header is required",
            status_code=400,
            retryable=False,
        )

    principal = state_str(request, "principal", "anonymous")
    return principal, request.url.path, key.strip()


def idempotency_replay(
    request: Request,
) -> tuple[JSONResponse | None, tuple[str, str, str]]:
    store = request.app.state.idempotency_store
    now = time.time()
    expired_keys = [key for key, record in store.items() if record["expires_at"] <= now]
    for key in expired_keys:
        del store[key]

    dedupe_key = idempotency_tuple(request)
    record = store.get(dedupe_key)
    if record is None:
        return None, dedupe_key

    return (
        JSONResponse(status_code=int(record["status_code"]), content=record["payload"]),
        dedupe_key,
    )


def store_idempotency_response(
    request: Request,
    dedupe_key: tuple[str, str, str],
    *,
    status_code: int,
    payload: dict[str, Any],
) -> None:
    ttl_s = request.app.state.settings.idempotency_ttl_seconds
    request.app.state.idempotency_store[dedupe_key] = {
        "status_code": status_code,
        "payload": payload,
        "expires_at": time.time() + ttl_s,
    }


def require_authenticated_principal(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> str:
    token = request.headers.get("X-Steersman-Token")
    if token is None or not secrets.compare_digest(token, settings.auth_token):
        raise AppError(
            kind="auth_denied",
            message="Authentication required",
            status_code=401,
            retryable=False,
        )

    principal = "local-user"
    request.state.principal = principal
    request.state.capabilities = request.app.state.skill_registry.all_capabilities()
    return principal


def manifest_capability_dependency(skill: str, operation: str):
    def _dependency(request: Request) -> None:
        registry = request.app.state.skill_registry
        try:
            capability = registry.capability_for(skill, operation)
        except KeyError as exc:
            raise AppError(
                kind="internal",
                message=str(exc),
                status_code=500,
                retryable=False,
            ) from exc
        policy.require(request, capability)

    return _dependency


def install_kernel(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request.state.request_id = uuid4().hex
        request.state.audit_ref = f"audit-{uuid4().hex}"
        request.state.principal = None
        request.state.capabilities = set()
        return await call_next(request)

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_envelope(
                request,
                kind=exc.kind,
                message=exc.message,
                retryable=exc.retryable,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        _: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_envelope(
                request,
                kind="invalid_input",
                message="Invalid request input",
                retryable=False,
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, _: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=error_envelope(
                request,
                kind="internal",
                message="Internal server error",
                retryable=True,
            ),
        )
