from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason_code: str
    details: str


def validate_outbound_text(text: str) -> PolicyDecision:
    candidate = text.strip()
    if not candidate:
        return PolicyDecision(
            allowed=False,
            reason_code="empty_reply",
            details="Outbound reply text cannot be empty.",
        )

    if len(candidate) > 4000:
        return PolicyDecision(
            allowed=False,
            reason_code="reply_too_long",
            details="Outbound reply exceeds WhatsApp body limit.",
        )

    return PolicyDecision(
        allowed=True,
        reason_code="pass",
        details="Reply passed baseline outbound checks.",
    )
