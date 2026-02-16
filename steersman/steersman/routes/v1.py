from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from steersman import audit
from steersman.errors import AppError
from steersman.kernel import idempotency_replay
from steersman.kernel import manifest_capability_dependency
from steersman.kernel import require_authenticated_principal
from steersman.kernel import result_envelope
from steersman.kernel import store_idempotency_response
from steersman.skills.imessage import list_imsg_chats
from steersman.skills.imessage import send_imsg_message
from steersman.skills.reminders import create_remindctl_reminder
from steersman.skills.reminders import list_remindctl_reminders


class NoteCreate(BaseModel):
    text: str


class ReminderCreate(BaseModel):
    title: str = Field(min_length=1)
    list: str | None = Field(default=None, min_length=1)
    due: str | None = None
    notes: str | None = None
    flagged: bool = False
    priority: int = Field(default=0, ge=0, le=9)


class IMessageSend(BaseModel):
    to: str = Field(min_length=1)
    text: str = Field(min_length=1)
    service: str = Field(default="auto")


DEFAULT_REMINDERS_LIST = "steerman"


def create_v1_router() -> APIRouter:
    v1 = APIRouter(prefix="/v1", dependencies=[Depends(require_authenticated_principal)])

    @v1.get(
        "/skills",
        dependencies=[Depends(manifest_capability_dependency("system", "catalog"))],
    )
    def list_skills(request: Request) -> dict:
        registry = request.app.state.skill_registry
        skills = [
            {
                "name": manifest.name,
                "version": manifest.version,
                "enabled": manifest.enabled,
            }
            for manifest in registry.list()
        ]
        return result_envelope(request, {"skills": skills})

    @v1.get(
        "/skills/{skill}/health",
        dependencies=[Depends(manifest_capability_dependency("system", "catalog"))],
    )
    def skill_health(skill: str, request: Request) -> dict:
        registry = request.app.state.skill_registry
        manifest = registry.get(skill)
        if manifest is None:
            raise AppError(
                kind="invalid_input",
                message=f"Unknown skill: {skill}",
                status_code=404,
                retryable=False,
            )
        return result_envelope(request, {"skill": manifest.name, "status": "ok"})

    @v1.get(
        "/skills/{skill}/requirements",
        dependencies=[Depends(manifest_capability_dependency("system", "catalog"))],
    )
    def skill_requirements(skill: str, request: Request) -> dict:
        registry = request.app.state.skill_registry
        manifest = registry.get(skill)
        if manifest is None:
            raise AppError(
                kind="invalid_input",
                message=f"Unknown skill: {skill}",
                status_code=404,
                retryable=False,
            )
        return result_envelope(
            request,
            {
                "skill": manifest.name,
                "requirements": manifest.requirements,
                "operation_capabilities": manifest.operation_capabilities,
            },
        )

    @v1.get(
        "/ping",
        dependencies=[Depends(manifest_capability_dependency("system", "ping"))],
    )
    def ping(request: Request) -> dict:
        audit.emit(
            request,
            action="v1.ping",
            capability="system.ping.read",
            outcome="allow",
        )
        return result_envelope(request, {"pong": "ok"})

    @v1.get(
        "/echo",
        dependencies=[Depends(manifest_capability_dependency("system", "echo"))],
    )
    def echo(message: str, request: Request) -> dict:
        audit.emit(
            request,
            action="v1.echo",
            capability="system.echo.read",
            outcome="allow",
            metadata={"message_len": len(message)},
        )
        return result_envelope(request, {"echo": message})

    @v1.post(
        "/notes",
        dependencies=[Depends(manifest_capability_dependency("notes", "create"))],
    )
    def create_note(payload: NoteCreate, request: Request) -> JSONResponse:
        replay, dedupe_key = idempotency_replay(request)
        if replay is not None:
            return replay

        note_id = uuid4().hex[:12]
        envelope = result_envelope(
            request,
            {
                "note_id": note_id,
                "text": payload.text,
            },
        )
        store_idempotency_response(
            request,
            dedupe_key,
            status_code=201,
            payload=envelope,
        )
        audit.emit(
            request,
            action="v1.notes.create",
            capability="notes.write",
            outcome="allow",
            metadata={"note_id": note_id},
        )
        return JSONResponse(status_code=201, content=envelope)

    @v1.get(
        "/reminders",
        dependencies=[Depends(manifest_capability_dependency("reminders", "list"))],
    )
    def list_reminders(
        request: Request,
        list: str | None = None,
        status: str | None = None,
    ) -> dict:
        list_name = list or DEFAULT_REMINDERS_LIST
        filtered_items = list_remindctl_reminders(list_name=list_name, status=status)
        audit.emit(
            request,
            action="v1.reminders.list",
            capability="reminders.read",
            outcome="allow",
            metadata={
                "count": len(filtered_items),
                "filters": {
                    "list": list_name,
                    "status": status,
                },
            },
        )
        return result_envelope(request, {"items": filtered_items})

    @v1.post(
        "/reminders",
        dependencies=[Depends(manifest_capability_dependency("reminders", "create"))],
    )
    def create_reminder(payload: ReminderCreate, request: Request) -> JSONResponse:
        replay, dedupe_key = idempotency_replay(request)
        if replay is not None:
            return replay

        list_name = payload.list.strip() if payload.list else DEFAULT_REMINDERS_LIST
        reminder = create_remindctl_reminder(
            list_name=list_name,
            title=payload.title,
            notes=payload.notes,
            due=payload.due,
            flagged=payload.flagged,
            priority=payload.priority,
        )
        envelope = result_envelope(request, {"item": reminder})
        store_idempotency_response(
            request,
            dedupe_key,
            status_code=201,
            payload=envelope,
        )
        audit.emit(
            request,
            action="v1.reminders.create",
            capability="reminders.write",
            outcome="allow",
            metadata={
                "reminder_id": reminder["id"],
                "list": list_name,
            },
        )
        return JSONResponse(status_code=201, content=envelope)

    @v1.get(
        "/imessage/chats",
        dependencies=[Depends(manifest_capability_dependency("imessage", "list_chats"))],
    )
    def list_imessage_chats(request: Request, limit: int = 20) -> dict:
        items = list_imsg_chats(limit=limit)

        audit.emit(
            request,
            action="v1.imessage.chats",
            capability="imessage.read",
            outcome="allow",
            metadata={"count": len(items)},
        )
        return result_envelope(request, {"items": items})

    @v1.post(
        "/imessage/send",
        dependencies=[Depends(manifest_capability_dependency("imessage", "send"))],
    )
    def send_imessage(payload: IMessageSend, request: Request) -> JSONResponse:
        replay, dedupe_key = idempotency_replay(request)
        if replay is not None:
            return replay

        result = send_imsg_message(
            to=payload.to.strip(),
            text=payload.text,
            service=payload.service,
        )

        envelope = result_envelope(request, result)
        store_idempotency_response(
            request,
            dedupe_key,
            status_code=201,
            payload=envelope,
        )
        audit.emit(
            request,
            action="v1.imessage.send",
            capability="imessage.send",
            outcome="allow",
            metadata={"to": payload.to, "service": payload.service},
        )
        return JSONResponse(status_code=201, content=envelope)

    return v1
