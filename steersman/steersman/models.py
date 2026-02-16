from typing import Any, Literal

from pydantic import BaseModel


class ErrorPayload(BaseModel):
    kind: Literal["auth_denied", "invalid_input", "dependency_unavailable", "internal"]
    message: str
    retryable: bool


class ActionEnvelope(BaseModel):
    request_id: str
    audit_ref: str
    result: Any | None = None
    error: ErrorPayload | None = None
