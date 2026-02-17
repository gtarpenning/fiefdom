from __future__ import annotations

import json
import logging
import uuid

from cupbearer.config import Settings
from cupbearer.db.connection import connect_sqlite
from cupbearer.db.repositories import SQLiteEventRepository
from cupbearer.domain.models import Event
from cupbearer.twilio import (
    TwilioAPIError,
    normalize_whatsapp_address,
    send_whatsapp_message,
)

logger = logging.getLogger(__name__)


class WhatsAppConfigError(RuntimeError):
    """Raised when WhatsApp sending is misconfigured."""


class WhatsAppDeliveryError(RuntimeError):
    """Raised when WhatsApp delivery attempt fails."""


def send_whatsapp_and_persist(
    *,
    settings: Settings,
    to: str,
    body: str,
    thread_id: str | None,
    contact_id: str | None,
    idempotency_key: str | None,
) -> tuple[Event, bool]:
    logger.info("send.start to=%s mode=%s chars=%d", to, settings.twilio_send_mode, len(body))
    if idempotency_key is not None:
        with connect_sqlite(settings.db_path) as connection:
            events = SQLiteEventRepository(connection)
            existing = events.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            existing_payload = json.loads(existing.payload)
            logger.info("send.dedup sid=%s", existing_payload.get("message_sid", "-")[:10])
            return existing, False

    if settings.twilio_send_mode == "mock":
        response_payload = {
            "sid": f"SM_MOCK_{uuid.uuid4().hex[:16]}",
            "status": "queued",
            "to": normalize_whatsapp_address(to),
            "from": normalize_whatsapp_address(settings.twilio_whatsapp_from or "whatsapp:+10000000000"),
            "body": body,
        }
    elif settings.twilio_send_mode == "live":
        if not settings.twilio_account_sid or not settings.twilio_auth_token or not settings.twilio_whatsapp_from:
            raise WhatsAppConfigError(
                "Twilio WhatsApp sender is not configured "
                "(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM)"
            )
        try:
            response_payload = send_whatsapp_message(
                account_sid=settings.twilio_account_sid,
                auth_token=settings.twilio_auth_token,
                from_whatsapp=settings.twilio_whatsapp_from,
                to_whatsapp=normalize_whatsapp_address(to),
                body=body,
            )
        except (TwilioAPIError, ValueError) as exc:
            logger.error("send.transport_error to=%s error=%s", to, exc)
            raise WhatsAppDeliveryError(str(exc)) from exc
    else:
        raise WhatsAppConfigError(
            f"Unsupported CUPBEARER_TWILIO_SEND_MODE '{settings.twilio_send_mode}'. "
            "Supported: live, mock"
        )

    event = Event(
        id=str(uuid.uuid4()),
        direction="outbound",
        source="twilio_whatsapp",
        type="whatsapp.message.sent",
        payload=json.dumps(
            {
                "message_sid": response_payload["sid"],
                "status": response_payload.get("status"),
                "to": response_payload.get("to"),
                "from": response_payload.get("from"),
                "body": response_payload.get("body"),
            },
            separators=(",", ":"),
        ),
        idempotency_key=idempotency_key,
        thread_id=thread_id,
        contact_id=contact_id or to,
    )

    with connect_sqlite(settings.db_path) as connection:
        events = SQLiteEventRepository(connection)
        persisted, created = events.append_idempotent(event)
    payload = json.loads(persisted.payload)
    logger.info("send.ok sid=%s status=%s", payload.get("message_sid", "-")[:10], payload.get("status", "-"))
    return persisted, created
