# Task 5: Persona Contract and Policy Enforcement

## Objective
Enforce the assistant personality and safety behavior as a hard runtime gate.

## Scope
- Implement strict persona contract:
  - business casual
  - witty/playful when appropriate
  - concise, on-topic, results-driven
- Implement safety/action policy checks before outbound sends.
- Add baseline response validation in centralized outbound path for v0.
- Keep one centralized outbound path so policy cannot be bypassed.
- Persist policy decisions in durable storage.

## Deliverables
- Policy validator module.
- Persona contract definition and checks.
- Policy decision logging.

## Acceptance Criteria
- No outbound message bypasses policy validator.
- Policy pass/fail and reason codes are persisted per outbound event.

## Deferred (Post-MVP)
- High-impact action confirmation gates (depends on task7 action runner).
- Richer persona scoring/rewriting loop.
