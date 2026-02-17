from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from time import monotonic
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cupbearer.config import Settings
from cupbearer.actions import ActionIntent

logger = logging.getLogger(__name__)

PERSONA_PROMPT = (
    "You are Cupbearer, a single-user personal assistant. "
    "Always respond in a business-casual tone, concise and results-driven. "
    "Be witty/playful only when it fits the user's message. "
    "Do not fabricate capabilities. "
    "Use the provided tools when the user's request requires them. "
    "Never output raw JSON, raw tool payloads, or audit/request IDs to the user; summarize tool results in plain language."
)

TOOLS = [
    {
        "name": "steersman_skills_list",
        "description": "List all available skills and their status on the local Steersman server.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "steersman_skills_health",
        "description": "Check the health of a specific skill.",
        "input_schema": {
            "type": "object",
            "properties": {"skill": {"type": "string", "description": "Skill name (e.g. 'reminders', 'imessage')"}},
            "required": ["skill"],
        },
    },
    {
        "name": "steersman_reminders_list",
        "description": "List reminders from Apple Reminders. Optionally filter by list name and status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "list": {"type": "string", "description": "Reminder list name to filter by"},
                "status": {"type": "string", "enum": ["open", "completed"], "description": "Filter by status"},
            },
            "required": [],
        },
    },
    {
        "name": "steersman_reminders_create",
        "description": "Create a new reminder in Apple Reminders.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Reminder title"},
                "list": {"type": "string", "description": "Reminder list name (defaults to 'steersman')"},
                "due": {"type": "string", "description": "Due date (e.g. 'tomorrow', '2026-02-20')"},
                "notes": {"type": "string", "description": "Additional notes"},
                "flagged": {"type": "boolean", "description": "Whether to flag the reminder"},
                "priority": {"type": "integer", "description": "Priority 0-9 (0=none)"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "steersman_imessage_chats",
        "description": "List recent iMessage chats.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max number of chats to return"},
            },
            "required": [],
        },
    },
    {
        "name": "steersman_imessage_send",
        "description": "Send an iMessage to a contact.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Phone number or contact name"},
                "text": {"type": "string", "description": "Message text to send"},
                "service": {"type": "string", "enum": ["auto", "sms", "iMessage"], "description": "Service to use"},
            },
            "required": ["to", "text"],
        },
    },
]

# Map from Claude tool names (underscores) to Steersman action names (dots)
_TOOL_TO_ACTION = {
    "steersman_skills_list": "steersman.skills.list",
    "steersman_skills_health": "steersman.skills.health",
    "steersman_reminders_list": "steersman.reminders.list",
    "steersman_reminders_create": "steersman.reminders.create",
    "steersman_imessage_chats": "steersman.imessage.chats",
    "steersman_imessage_send": "steersman.imessage.send",
}


@dataclass(frozen=True)
class AgentTurnInput:
    user_message: str
    thread_id: str | None
    contact_id: str | None
    memory_context: str | None = None


@dataclass(frozen=True)
class AgentTurnOutput:
    reply_text: str
    provider: str
    model: str
    action_intent: ActionIntent | None = None
    # Internal: preserved for tool result follow-up
    _tool_use_id: str | None = None
    _assistant_content: list[dict] | None = None


class AgentAdapter(Protocol):
    def run_turn(self, turn_input: AgentTurnInput) -> AgentTurnOutput:
        """Generate one assistant reply for a user turn."""

    def run_turn_with_tool_result(
        self,
        turn_input: AgentTurnInput,
        *,
        tool_name: str,
        tool_response: dict[str, object],
        tool_use_id: str | None = None,
        assistant_content: list[dict] | None = None,
        prior_messages: list[dict] | None = None,
    ) -> AgentTurnOutput:
        """Generate follow-up reply after a tool call returns.

        When *prior_messages* is provided the adapter uses that accumulated
        conversation history directly (for multi-round tool chaining).
        Otherwise it builds a single-round conversation from *turn_input*.
        """


def _build_system_prompt(memory_context: str | None) -> str:
    if not memory_context:
        return PERSONA_PROMPT
    return (
        PERSONA_PROMPT
        + "\n\nRelevant memories about this user:\n"
        + memory_context
    )


class ClaudeAPIError(RuntimeError):
    """Raised when the Claude API request fails."""


def _call_claude(
    *,
    api_key: str,
    base_url: str,
    model: str,
    system: str,
    messages: list[dict],
    timeout: float,
    tools: list[dict] | None = None,
) -> dict:
    started = monotonic()
    payload: dict = {
        "model": model,
        "max_tokens": 1024,
        "system": system,
        "messages": messages,
    }
    if tools:
        payload["tools"] = tools

    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    logger.info("claude.req model=%s msgs=%d tools=%d", model, len(messages), len(tools) if tools else 0)
    request = Request(
        f"{base_url.rstrip('/')}/v1/messages",
        method="POST",
        data=raw,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
            logger.info("claude.res stop=%s dur=%dms", body.get("stop_reason", "-"), (monotonic() - started) * 1000)
            return body
    except HTTPError as err:
        details = err.read().decode("utf-8")
        raise ClaudeAPIError(f"Claude API failed ({err.code}): {details}") from err
    except URLError as err:
        raise ClaudeAPIError(f"Claude API request failed: {err}") from err


class ClaudeAdapter:
    def __init__(self, settings: Settings):
        self._settings = settings

    def run_turn(self, turn_input: AgentTurnInput) -> AgentTurnOutput:
        logger.info("run.start thread=%s chars=%d", turn_input.thread_id, len(turn_input.user_message))
        if self._settings.claude_mock_response is not None:
            parsed_mock: object
            try:
                parsed_mock = json.loads(self._settings.claude_mock_response)
            except json.JSONDecodeError:
                parsed_mock = None

            if isinstance(parsed_mock, dict):
                reply_text = str(parsed_mock.get("reply_text", "")).strip() or "Working on it..."
                tool_call = parsed_mock.get("tool_call")
                if isinstance(tool_call, dict):
                    tool_name = tool_call.get("name")
                    tool_arguments = tool_call.get("arguments", {})
                    if isinstance(tool_name, str) and tool_name.strip() and isinstance(tool_arguments, dict):
                        logger.info(
                            "run.mock.tool_call name=%s args_keys=%s",
                            tool_name.strip(),
                            ",".join(sorted(tool_arguments.keys())) if tool_arguments else "-",
                        )
                        return AgentTurnOutput(
                            reply_text=reply_text,
                            provider="claude",
                            model=self._settings.claude_model,
                            action_intent=ActionIntent(name=tool_name.strip(), arguments=tool_arguments),
                        )

            logger.info("run.mock.text_response")
            return AgentTurnOutput(
                reply_text=self._settings.claude_mock_response,
                provider="claude",
                model=self._settings.claude_model,
            )

        if not self._settings.claude_api_key:
            raise ClaudeAPIError("Missing ANTHROPIC_API_KEY")

        body = _call_claude(
            api_key=self._settings.claude_api_key,
            base_url=self._settings.claude_base_url,
            model=self._settings.claude_model,
            system=_build_system_prompt(turn_input.memory_context),
            messages=[{"role": "user", "content": turn_input.user_message}],
            timeout=self._settings.claude_timeout_seconds,
            tools=TOOLS,
        )

        return self._parse_response(body)

    def run_turn_with_tool_result(
        self,
        turn_input: AgentTurnInput,
        *,
        tool_name: str,
        tool_response: dict[str, object],
        tool_use_id: str | None = None,
        assistant_content: list[dict] | None = None,
        prior_messages: list[dict] | None = None,
    ) -> AgentTurnOutput:
        logger.info("followup.start tool=%s", tool_name)
        if self._settings.claude_mock_tool_followup_response is not None:
            logger.info("followup.mock.text_response")
            return AgentTurnOutput(
                reply_text=self._settings.claude_mock_tool_followup_response,
                provider="claude",
                model=self._settings.claude_model,
            )

        if not self._settings.claude_api_key:
            raise ClaudeAPIError("Missing ANTHROPIC_API_KEY")

        if prior_messages is not None:
            # Multi-round: caller already accumulated the full history.
            messages = prior_messages
            logger.info("followup.prior_messages turns=%d", len(messages))
        else:
            # Single-round fallback: build from scratch.
            messages = [
                {"role": "user", "content": turn_input.user_message},
            ]

            if assistant_content and tool_use_id:
                logger.info("followup.tool_result_flow blocks=%d", len(assistant_content))
                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": json.dumps(tool_response, separators=(",", ":")),
                    }],
                })
            else:
                logger.info("followup.fallback_flow")
                messages.append({
                    "role": "assistant",
                    "content": f"I called the {tool_name} tool.",
                })
                messages.append({
                    "role": "user",
                    "content": f"Tool result: {json.dumps(tool_response, separators=(',', ':'))}\n\nPlease summarize this for me.",
                })

        body = _call_claude(
            api_key=self._settings.claude_api_key,
            base_url=self._settings.claude_base_url,
            model=self._settings.claude_model,
            system=_build_system_prompt(turn_input.memory_context),
            messages=messages,
            timeout=self._settings.claude_timeout_seconds,
            tools=TOOLS,
        )

        return self._parse_response(body)

    def _parse_response(self, body: dict) -> AgentTurnOutput:
        content = body.get("content", [])
        model = body.get("model", self._settings.claude_model)
        stop_reason = body.get("stop_reason", "end_turn")

        # Extract text blocks
        text_parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        reply_text = "".join(text_parts).strip()

        # Check for tool_use blocks
        tool_use_block = None
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tool_use_block = block
                break

        if tool_use_block and stop_reason == "tool_use":
            tool_name = tool_use_block["name"]
            tool_input = tool_use_block.get("input", {})
            tool_use_id = tool_use_block.get("id")
            action_name = _TOOL_TO_ACTION.get(tool_name, tool_name)
            logger.info("parse.tool_use tool=%s action=%s", tool_name, action_name)

            return AgentTurnOutput(
                reply_text=reply_text or "Working on it...",
                provider="claude",
                model=model,
                action_intent=ActionIntent(name=action_name, arguments=tool_input),
                _tool_use_id=tool_use_id,
                _assistant_content=content,
            )

        if not reply_text:
            raise ClaudeAPIError("Claude API returned empty text response")
        logger.info("parse.text_reply chars=%d", len(reply_text))

        return AgentTurnOutput(
            reply_text=reply_text,
            provider="claude",
            model=model,
        )


class CodexStubAdapter:
    def run_turn(self, turn_input: AgentTurnInput) -> AgentTurnOutput:
        del turn_input
        return AgentTurnOutput(
            reply_text="Codex stub adapter is not enabled for runtime use.",
            provider="codex_stub",
            model="stub",
        )

    def run_turn_with_tool_result(
        self,
        turn_input: AgentTurnInput,
        *,
        tool_name: str,
        tool_response: dict[str, object],
        tool_use_id: str | None = None,
        assistant_content: list[dict] | None = None,
        prior_messages: list[dict] | None = None,
    ) -> AgentTurnOutput:
        del turn_input, tool_name, tool_response, tool_use_id, assistant_content, prior_messages
        return AgentTurnOutput(
            reply_text="Codex stub adapter is not enabled for runtime use.",
            provider="codex_stub",
            model="stub",
        )


def build_agent_adapter(settings: Settings) -> AgentAdapter:
    if settings.agent_provider == "claude":
        return ClaudeAdapter(settings)
    if settings.agent_provider == "codex_stub":
        return CodexStubAdapter()
    raise RuntimeError(
        "Unsupported CUPBEARER_AGENT_PROVIDER "
        f"'{settings.agent_provider}'. Supported: claude, codex_stub"
    )
