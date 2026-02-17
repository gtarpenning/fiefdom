# Task 6: Agent Orchestration Loop

## Objective
Implement the lightweight but complete agent loop for message turns.

## Scope
- Implement orchestrator flow:
  - ingest event
  - load minimal thread context
  - run agent turn
  - optional action intent dispatch (deferred in v0)
  - policy validation
  - outbound send
  - persist resulting events/audits
- Keep orchestration explicit and easy to inspect.
- Keep retries/idempotency compatible with transport and action runner.

## Deliverables
- Orchestrator module for end-to-end message turns.
- Structured turn result contract used by transport/policy/action layers.
- Event and audit persistence hooks.

## Acceptance Criteria
- A single inbound message can complete a full agent turn with audited output.
- Orchestrator handles no-action turns deterministically.
- Failed turns are traceable with sufficient diagnostics.

## Deferred (Post-MVP)
- Action intent dispatch integration (task7).
- Extended context windows and memory injection (task8).
