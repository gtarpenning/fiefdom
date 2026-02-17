# Task 7: External Endpoint Action Runner

## Objective
Enable tool/action execution exclusively through external HTTP endpoint contracts.

## Scope
- Implement explicit endpoint allowlist (`/v1/...`) for callable actions.
- Add auth injection, timeout controls, and idempotency key propagation.
- Validate basic request/response shape at Cupbearer boundary.
- Persist every action call to durable event/audit data.
- Keep Cupbearer free of downstream business-task logic.

## Deliverables
- Action runner/client module for external endpoints.
- Endpoint contract definitions with explicit allowlist.
- Action call persistence integration.

## Acceptance Criteria
- Allowed endpoints can be called from agent turns.
- Every action call is fully traceable in audit data.

## MVP Slice Implemented
- Allowlisted Steersman calls:
  - `steersman.skills.list`
  - `steersman.skills.health`
  - `steersman.skills.requirements`
  - `steersman.reminders.list`
  - `steersman.reminders.create`
  - `steersman.imessage.chats`
  - `steersman.imessage.send`
- Agent may emit one tool call intent per turn; orchestrator executes it and logs an action event.

## Deferred (Post-MVP)
- Retry/backoff inside action runner.
- Strict per-action request/response schema validation.
- Dedicated `action_audit` repository/table beyond event-log entries.
