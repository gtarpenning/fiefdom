from __future__ import annotations

from cupbearer.config import Settings
from cupbearer.domain.models import Event
from cupbearer.whatsapp_service import send_whatsapp_and_persist

TOOL_SUCCESS_REACTION_EMOJI = "✅"


def send_tool_success_reaction(
    *,
    settings: Settings,
    inbound_event: Event,
    to_whatsapp: str,
) -> tuple[Event, bool]:
    return send_whatsapp_and_persist(
        settings=settings,
        to=to_whatsapp,
        body=TOOL_SUCCESS_REACTION_EMOJI,
        thread_id=inbound_event.thread_id,
        contact_id=inbound_event.contact_id,
        idempotency_key=f"twilio:whatsapp:outbound:reaction:tool-success:{inbound_event.id}",
    )
