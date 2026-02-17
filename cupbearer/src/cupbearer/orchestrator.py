from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass

from cupbearer.actions import SteersmanActionRunner
from cupbearer.agent import AgentAdapter, AgentTurnInput
from cupbearer.memory import search_memories, store_memories
from cupbearer.config import Settings
from cupbearer.db.connection import connect_sqlite
from cupbearer.db.repositories import SQLiteEventRepository
from cupbearer.domain.models import Event, Job
from cupbearer.logging import event_id_ctx
from cupbearer.policy import validate_outbound_text
from cupbearer.whatsapp_reactions import send_tool_success_reaction
from cupbearer.whatsapp_service import send_whatsapp_and_persist

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5


def _looks_like_structured_payload(text: str) -> bool:
    raw = text.strip()
    if not raw:
        return False
    if raw.startswith("```") and raw.endswith("```"):
        lines = raw.splitlines()
        if len(lines) >= 3:
            raw = "\n".join(lines[1:-1]).strip()
    if (raw.startswith("{") and raw.endswith("}")) or (
        raw.startswith("[") and raw.endswith("]")
    ):
        try:
            parsed = json.loads(raw)
            return isinstance(parsed, dict | list)
        except json.JSONDecodeError:
            return False
    return False


def _sanitize_outbound_reply(reply_text: str, *, had_action: bool, last_action_ok: bool) -> str:
    if not _looks_like_structured_payload(reply_text):
        return reply_text
    logger.warning("turn.reply.sanitized_raw_payload")
    if had_action and last_action_ok:
        return "Done. I ran that action successfully."
    if had_action and not last_action_ok:
        return "I tried to run that action, but it failed."
    return "I can help with that. Tell me what outcome you want, and I'll handle it."


@dataclass(frozen=True)
class AgentOrchestrator:
    settings: Settings
    agent_adapter: AgentAdapter
    action_runner: SteersmanActionRunner
    memory: object | None = None  # mem0 Memory instance, or None if disabled

    def handle_turn_job(self, job: Job) -> None:
        turn_started = time.monotonic()
        payload = json.loads(job.payload)
        inbound_event_id = payload.get("inbound_event_id")
        if not isinstance(inbound_event_id, str) or not inbound_event_id:
            raise RuntimeError("agent.turn payload missing inbound_event_id")
        event_token = event_id_ctx.set(inbound_event_id)
        logger.info("turn.start job=%s", job.id[:8])
        try:
            self._handle_turn_job_inner(job, inbound_event_id)
            logger.info("turn.done job=%s dur=%dms", job.id[:8], (time.monotonic() - turn_started) * 1000)
        finally:
            event_id_ctx.reset(event_token)

    def _handle_turn_job_inner(self, job: Job, inbound_event_id: str) -> None:
        del job

        with connect_sqlite(self.settings.db_path) as connection:
            events = SQLiteEventRepository(connection)
            inbound_event = events.get(inbound_event_id)
        if inbound_event is None:
            raise RuntimeError(f"inbound event not found: {inbound_event_id}")

        inbound_payload = json.loads(inbound_event.payload)
        incoming_text = str(inbound_payload.get("Body", "")).strip()
        from_address = str(inbound_payload.get("From", "")).strip()
        logger.info("turn.inbound thread=%s from=%s chars=%d", inbound_event.thread_id, from_address, len(incoming_text))
        if not incoming_text or not from_address:
            logger.warning("turn.skipped missing_text_or_from")
            return

        # Retrieve relevant memories for this user (if mem0 is enabled).
        memory_context: str | None = None
        if self.memory is not None and inbound_event.contact_id:
            memory_context = search_memories(
                self.memory,
                user_id=inbound_event.contact_id,
                query=incoming_text,
            )
            if memory_context:
                logger.info("turn.memory.injected chars=%d", len(memory_context))

        turn_input = AgentTurnInput(
            user_message=incoming_text,
            thread_id=inbound_event.thread_id,
            contact_id=inbound_event.contact_id,
            memory_context=memory_context,
        )

        llm_started = time.monotonic()
        logger.info("turn.llm.start")
        turn_result = self.agent_adapter.run_turn(turn_input)
        action_name = turn_result.action_intent.name if turn_result.action_intent else "-"
        logger.info(
            "turn.llm.result model=%s action=%s reply_chars=%d dur=%dms",
            turn_result.model, action_name, len(turn_result.reply_text),
            (time.monotonic() - llm_started) * 1000,
        )

        reply_text = turn_result.reply_text
        had_action = turn_result.action_intent is not None
        last_action_ok = False
        if turn_result.action_intent is not None:
            messages: list[dict] = [{"role": "user", "content": incoming_text}]
            current = turn_result

            for tool_round in range(MAX_TOOL_ROUNDS):
                intent = current.action_intent
                assert intent is not None  # loop guard
                logger.info("turn.tool.call round=%d name=%s", tool_round, intent.name)

                action_idempotency = (
                    f"action:steersman:{inbound_event.id}:{intent.name}:{tool_round}"
                )
                action_started = time.monotonic()
                action_result = self.action_runner.run(
                    intent,
                    idempotency_key=action_idempotency,
                )
                last_action_ok = action_result.ok
                logger.info(
                    "turn.tool.result round=%d name=%s ok=%s status=%s dur=%dms",
                    tool_round, action_result.name, action_result.ok,
                    action_result.status_code, (time.monotonic() - action_started) * 1000,
                )

                action_event = Event(
                    id=str(uuid.uuid4()),
                    direction="outbound",
                    source="action_runner",
                    type="action.steersman.executed",
                    payload=json.dumps(
                        {
                            "inbound_event_id": inbound_event.id,
                            "action_name": action_result.name,
                            "ok": action_result.ok,
                            "status_code": action_result.status_code,
                            "response": action_result.response,
                        },
                        separators=(",", ":"),
                    ),
                    idempotency_key=action_idempotency,
                    thread_id=inbound_event.thread_id,
                    contact_id=inbound_event.contact_id,
                )
                with connect_sqlite(self.settings.db_path) as connection:
                    events = SQLiteEventRepository(connection)
                    events.append_idempotent(action_event)
                logger.info("turn.tool.persisted round=%d", tool_round)

                if tool_round == 0 and action_result.ok:
                    try:
                        reaction_event, reaction_created = send_tool_success_reaction(
                            settings=self.settings,
                            inbound_event=inbound_event,
                            to_whatsapp=from_address,
                        )
                        logger.info("turn.tool.reaction sent=%s", reaction_created)
                    except Exception:  # noqa: BLE001
                        logger.exception("turn.tool.reaction.failed (non-fatal)")

                # Accumulate conversation history for Claude
                if current._assistant_content and current._tool_use_id:
                    messages.append({"role": "assistant", "content": current._assistant_content})
                    messages.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": current._tool_use_id,
                            "content": json.dumps(action_result.response, separators=(",", ":")),
                        }],
                    })

                try:
                    followup_started = time.monotonic()
                    followup = self.agent_adapter.run_turn_with_tool_result(
                        turn_input,
                        tool_name=action_result.name,
                        tool_response=action_result.response,
                        tool_use_id=current._tool_use_id,
                        assistant_content=current._assistant_content,
                        prior_messages=messages,
                    )
                    reply_text = followup.reply_text
                    followup_action = followup.action_intent.name if followup.action_intent else "-"
                    logger.info(
                        "turn.tool.followup round=%d action=%s reply_chars=%d dur=%dms",
                        tool_round, followup_action, len(followup.reply_text),
                        (time.monotonic() - followup_started) * 1000,
                    )
                except Exception:  # noqa: BLE001
                    logger.exception("turn.tool.followup.failed round=%d", tool_round)
                    if last_action_ok:
                        reply_text = "Done. I ran the requested action successfully."
                    else:
                        reply_text = "I tried to run that action, but it failed."
                    break

                if followup.action_intent is None:
                    break

                current = followup
            else:
                logger.warning("turn.tool.max_rounds rounds=%d", MAX_TOOL_ROUNDS)

        reply_text = _sanitize_outbound_reply(
            reply_text,
            had_action=had_action,
            last_action_ok=last_action_ok,
        )

        policy_decision = validate_outbound_text(reply_text)
        logger.info("turn.policy allowed=%s reason=%s", policy_decision.allowed, policy_decision.reason_code)
        policy_event = Event(
            id=str(uuid.uuid4()),
            direction="outbound",
            source="policy",
            type="policy.outbound.decision",
            payload=json.dumps(
                {
                    "inbound_event_id": inbound_event.id,
                    "allowed": policy_decision.allowed,
                    "reason_code": policy_decision.reason_code,
                    "details": policy_decision.details,
                    "provider": turn_result.provider,
                    "model": turn_result.model,
                },
                separators=(",", ":"),
            ),
            idempotency_key=f"policy:outbound:{inbound_event.id}",
            thread_id=inbound_event.thread_id,
            contact_id=inbound_event.contact_id,
        )
        with connect_sqlite(self.settings.db_path) as connection:
            events = SQLiteEventRepository(connection)
            events.append_idempotent(policy_event)
        if not policy_decision.allowed:
            logger.warning("turn.blocked_by_policy")
            return

        outbound_idempotency = f"twilio:whatsapp:outbound:reply:{inbound_event.id}"
        outbound_event, outbound_created = send_whatsapp_and_persist(
            settings=self.settings,
            to=from_address,
            body=reply_text,
            thread_id=inbound_event.thread_id,
            contact_id=inbound_event.contact_id,
            idempotency_key=outbound_idempotency,
        )
        outbound_payload = json.loads(outbound_event.payload)
        logger.info(
            "turn.outbound sid=%s status=%s chars=%d",
            outbound_payload.get("message_sid", "-")[:10],
            outbound_payload.get("status", "-"),
            len(reply_text),
        )

        # Store conversation into mem0 AFTER the reply is already delivered.
        # PERF: add() makes 2 LLM calls (~1-2s) for fact extraction + dedup.
        # This is fine because the user already has their reply. Future: move
        # to a "memory.store" background job or use AsyncMemory.
        if self.memory is not None and inbound_event.contact_id:
            store_memories(
                self.memory,
                user_id=inbound_event.contact_id,
                messages=[
                    {"role": "user", "content": incoming_text},
                    {"role": "assistant", "content": reply_text},
                ],
            )
