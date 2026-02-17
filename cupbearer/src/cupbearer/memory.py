from __future__ import annotations

import logging
from typing import Any

from cupbearer.config import Settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PERFORMANCE NOTES
#
# search() cost: 1 embedding call + vector lookup (~100-200ms). Runs before
#   the LLM call so it's on the critical path. Consider caching recent
#   searches per contact_id if this becomes a bottleneck.
#
# add() cost: 2 LLM calls internally (fact extraction + dedup decision,
#   ~1-2s). We call it AFTER the WhatsApp reply is already sent so the user
#   never waits. Future improvements:
#   - Move to a dedicated "memory.store" background job via the job worker.
#   - Use mem0 AsyncMemory for true non-blocking writes.
#   - Pass full multi-turn conversation (including tool calls) instead of
#     just the final user message + assistant reply for richer extraction.
#
# Embedder: Using OpenAI text-embedding-3-small (requires OPENAI_API_KEY).
#   To eliminate the OpenAI dependency, switch to the "huggingface" provider
#   with a local sentence-transformers model (~500MB download, zero API cost).
#
# Fact extraction LLM: Using claude-haiku-4-5-20251001 (cheapest Anthropic
#   model). Could swap for a local model via ollama to reduce cost to zero.
# ---------------------------------------------------------------------------


def build_memory(settings: Settings) -> Any | None:
    """Build a mem0 Memory instance from settings, or None if disabled."""
    if not settings.mem0_enabled:
        return None

    try:
        from mem0 import Memory
    except ImportError:
        logger.error("mem0ai package not installed but CUPBEARER_MEM0_ENABLED=1")
        return None

    if not settings.claude_api_key:
        logger.error("mem0 requires ANTHROPIC_API_KEY for fact extraction LLM")
        return None

    if not settings.openai_api_key:
        logger.error("mem0 requires OPENAI_API_KEY for embeddings")
        return None

    # config = {
    #     "vector_store": {
    #         "provider": "qdrant",
    #         "config": {"path": settings.mem0_storage_path},
    #     },
    #     "llm": {
    #         "provider": "anthropic",
    #         "config": {
    #             "model": "claude-haiku-4-5-20251001",
    #             "api_key": settings.claude_api_key,
    #         },
    #     },
    #     "embedder": {
    #         "provider": "openai",
    #         "config": {
    #             "model": "text-embedding-3-small",
    #             "api_key": settings.openai_api_key,
    #         },
    #     },
    # }

    # memory = Memory.
    memory = Memory()
    logger.info("mem0.init storage_path=%s", settings.mem0_storage_path)
    return memory


def search_memories(memory: Any, user_id: str, query: str) -> str | None:
    """Retrieve relevant memories for a user, formatted for injection into
    the system prompt. Returns None if no memories found."""
    try:
        result = memory.search(query=query, user_id=user_id, limit=5)
        memories = result.get("results", [])
        if not memories:
            return None
        lines = [f"- {m['memory']}" for m in memories if m.get("memory")]
        if not lines:
            return None
        formatted = "\n".join(lines)
        logger.info("mem0.search user=%s results=%d", user_id, len(lines))
        return formatted
    except Exception:  # noqa: BLE001
        logger.exception("mem0.search.failed user_id=%s", user_id)
        return None


def store_memories(
    memory: Any,
    user_id: str,
    messages: list[dict[str, str]],
) -> None:
    """Store conversation messages into mem0 for future recall.

    Called AFTER the reply is sent to the user so latency doesn't matter.
    """
    try:
        result = memory.add(messages, user_id=user_id)
        events = result.get("results", [])
        added = sum(1 for e in events if e.get("event") == "ADD")
        updated = sum(1 for e in events if e.get("event") == "UPDATE")
        logger.info("mem0.store user=%s added=%d updated=%d", user_id, added, updated)
    except Exception:  # noqa: BLE001
        logger.exception("mem0.store.failed user_id=%s", user_id)
