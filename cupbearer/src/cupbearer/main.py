from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any, Literal
from urllib.parse import parse_qsl

from fastapi import FastAPI, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field

from cupbearer.actions import SteersmanActionRunner
from cupbearer.agent import build_agent_adapter
from cupbearer.memory import build_memory
from cupbearer.config import Settings, load_settings
from cupbearer.db import connect_sqlite, init_database
from cupbearer.db.repositories import SQLiteEventRepository, SQLiteJobRepository
from cupbearer.domain.models import Event, Job
from cupbearer.logging import configure_logging, correlation_id_middleware
from cupbearer.orchestrator import AgentOrchestrator
from cupbearer.time_utils import utc_now_sqlite
from cupbearer.twilio import (
    validate_signature,
)
from cupbearer.whatsapp_service import (
    WhatsAppConfigError,
    WhatsAppDeliveryError,
    send_whatsapp_and_persist,
)
from cupbearer.worker import JobWorker

logger = logging.getLogger(__name__)


class IngestEventRequest(BaseModel):
    source: str
    type: str
    payload: dict[str, Any]
    direction: Literal["inbound", "outbound"] = "inbound"
    thread_id: str | None = None
    contact_id: str | None = None
    idempotency_key: str | None = None


class IngestEventResponse(BaseModel):
    event_id: str
    deduplicated: bool


class EnqueueJobRequest(BaseModel):
    type: str = Field(
        ...,
        min_length=1,
        max_length=64,
    )
    payload: dict[str, Any]
    max_retries: int = Field(default=5, ge=0, le=20)
    idempotency_key: str | None = None


class EnqueueJobResponse(BaseModel):
    job_id: str
    status: str
    deduplicated: bool


class JobResponse(BaseModel):
    id: str
    type: str
    payload: dict[str, Any]
    status: str
    retry_count: int
    max_retries: int
    available_at: str
    last_error: str | None
    idempotency_key: str | None


class WhatsAppSendRequest(BaseModel):
    to: str = Field(..., min_length=3)
    body: str = Field(..., min_length=1, max_length=4000)
    thread_id: str | None = None
    contact_id: str | None = None
    idempotency_key: str | None = None


class WhatsAppSendResponse(BaseModel):
    message_sid: str
    event_id: str
    deduplicated: bool
    status: str | None


class TwilioWebhookResponse(BaseModel):
    event_id: str
    deduplicated: bool


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = load_settings()
    app.state.settings = settings
    app.state.is_ready = False

    configure_logging(settings.log_level)
    logger.info("Starting %s in %s", settings.service_name, settings.env)
    applied_migrations = init_database(settings.db_path)
    if applied_migrations:
        logger.info("Applied migrations: %s", ",".join(applied_migrations))
    else:
        logger.info("No pending migrations")

    worker = JobWorker(
        db_path=settings.db_path,
        poll_interval_seconds=settings.worker_poll_interval_seconds,
        retry_base_seconds=settings.worker_retry_base_seconds,
        retry_max_seconds=settings.worker_retry_max_seconds,
    )
    agent_adapter = build_agent_adapter(settings)
    action_runner = SteersmanActionRunner(settings=settings)
    memory = build_memory(settings)
    orchestrator = AgentOrchestrator(
        settings=settings,
        agent_adapter=agent_adapter,
        action_runner=action_runner,
        memory=memory,
    )
    worker.register_handler("agent.turn", orchestrator.handle_turn_job)
    app.state.worker = worker
    worker_task = asyncio.create_task(worker.run_forever())

    app.state.is_ready = True
    logger.info("Service marked ready")

    try:
        yield
    finally:
        app.state.is_ready = False
        worker.stop()
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        logger.info("Service marked not ready")


app = FastAPI(title="Cupbearer", lifespan=lifespan)
app.middleware("http")(correlation_id_middleware)


@app.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready() -> dict[str, str]:
    if not getattr(app.state, "is_ready", False):
        return {"status": "not_ready"}
    return {"status": "ready"}


@app.post("/ingest/events", response_model=IngestEventResponse)
def ingest_event(
    request: IngestEventRequest,
    x_idempotency_key: str | None = Header(default=None),
) -> IngestEventResponse:
    settings: Settings = app.state.settings
    idempotency_key = request.idempotency_key or x_idempotency_key
    event = Event(
        id=str(uuid.uuid4()),
        direction=request.direction,
        source=request.source,
        type=request.type,
        payload=json.dumps(request.payload, separators=(",", ":")),
        idempotency_key=idempotency_key,
        thread_id=request.thread_id,
        contact_id=request.contact_id,
    )

    with connect_sqlite(settings.db_path) as connection:
        events = SQLiteEventRepository(connection)
        persisted, created = events.append_idempotent(event)

    return IngestEventResponse(event_id=persisted.id, deduplicated=not created)


@app.post("/jobs", response_model=EnqueueJobResponse)
def enqueue_job(
    request: EnqueueJobRequest,
    x_idempotency_key: str | None = Header(default=None),
) -> EnqueueJobResponse:
    settings: Settings = app.state.settings
    worker: JobWorker = app.state.worker
    if not worker.has_handler(request.type):
        supported = ", ".join(worker.supported_job_types())
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported job type '{request.type}'. Supported: {supported}",
        )

    idempotency_key = request.idempotency_key or x_idempotency_key
    job = Job(
        id=str(uuid.uuid4()),
        type=request.type,
        payload=json.dumps(request.payload, separators=(",", ":")),
        status="pending",
        retry_count=0,
        max_retries=request.max_retries,
        available_at=utc_now_sqlite(),
        idempotency_key=idempotency_key,
    )

    with connect_sqlite(settings.db_path) as connection:
        jobs = SQLiteJobRepository(connection)
        persisted, created = jobs.enqueue(job)

    return EnqueueJobResponse(
        job_id=persisted.id,
        status=persisted.status,
        deduplicated=not created,
    )


@app.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str) -> JobResponse:
    settings: Settings = app.state.settings
    with connect_sqlite(settings.db_path) as connection:
        jobs = SQLiteJobRepository(connection)
        job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job_not_found")
    return JobResponse(
        id=job.id,
        type=job.type,
        payload=json.loads(job.payload),
        status=job.status,
        retry_count=job.retry_count,
        max_retries=job.max_retries,
        available_at=job.available_at,
        last_error=job.last_error,
        idempotency_key=job.idempotency_key,
    )


@app.post("/channels/twilio/whatsapp/webhook")
async def ingest_twilio_whatsapp_webhook(
    request: Request,
    x_twilio_signature: str | None = Header(default=None),
) -> Response:
    settings: Settings = app.state.settings
    if settings.twilio_webhook_validate_signature:
        if not settings.twilio_auth_token:
            raise HTTPException(
                status_code=503,
                detail="Twilio webhook auth is not configured (missing TWILIO_AUTH_TOKEN)",
            )

    raw_body = (await request.body()).decode("utf-8")
    params = {k: v for k, v in parse_qsl(raw_body, keep_blank_values=True)}
    message_sid = params.get("MessageSid")
    from_address = params.get("From")

    if settings.twilio_webhook_validate_signature:
        is_valid = validate_signature(
            url=str(request.url),
            params=params,
            auth_token=settings.twilio_auth_token or "",
            provided_signature=x_twilio_signature,
        )
        if not is_valid:
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    idempotency_key = (
        f"twilio:whatsapp:inbound:{message_sid}"
        if message_sid
        else f"twilio:whatsapp:inbound:{uuid.uuid4()}"
    )
    event = Event(
        id=str(uuid.uuid4()),
        direction="inbound",
        source="twilio_whatsapp",
        type="whatsapp.message.received",
        payload=json.dumps(params, separators=(",", ":")),
        idempotency_key=idempotency_key,
        thread_id=from_address,
        contact_id=from_address,
    )

    with connect_sqlite(settings.db_path) as connection:
        events = SQLiteEventRepository(connection)
        persisted, created = events.append_idempotent(event)
        jobs = SQLiteJobRepository(connection)
        jobs.enqueue(
            Job(
                id=str(uuid.uuid4()),
                type="agent.turn",
                payload=json.dumps({"inbound_event_id": persisted.id}, separators=(",", ":")),
                status="pending",
                retry_count=0,
                max_retries=0,
                available_at=utc_now_sqlite(),
                idempotency_key=f"agent:turn:{persisted.id}",
            )
        )

    return Response(
        content="<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response></Response>",
        media_type="text/xml",
        headers={
            "X-Cupbearer-Event-Id": persisted.id,
            "X-Cupbearer-Deduplicated": "true" if not created else "false",
        },
    )


@app.post("/channels/whatsapp/send", response_model=WhatsAppSendResponse)
def send_whatsapp(
    request: WhatsAppSendRequest,
    x_idempotency_key: str | None = Header(default=None),
) -> WhatsAppSendResponse:
    settings: Settings = app.state.settings
    idempotency_key = request.idempotency_key or x_idempotency_key
    try:
        persisted, created = send_whatsapp_and_persist(
            settings=settings,
            to=request.to,
            body=request.body,
            thread_id=request.thread_id,
            contact_id=request.contact_id,
            idempotency_key=idempotency_key,
        )
    except WhatsAppConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except WhatsAppDeliveryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    payload = json.loads(persisted.payload)
    return WhatsAppSendResponse(
        message_sid=payload["message_sid"],
        event_id=persisted.id,
        deduplicated=not created,
        status=payload.get("status"),
    )
