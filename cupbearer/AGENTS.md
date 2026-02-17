# Cupbearer Agent Context

## Project Purpose
Cupbearer is a single-tenant personal assistant monolith focused on the **agent layer**: message in, smart persona-driven reasoning, endpoint action calls, message out.

## Core Product Constraints
- Single tenant only.
- Event-first architecture with immutable event logging.
- Idempotent webhooks and retriable outbound action calls.
- Mandatory persona and safety policy checks before outbound responses/actions.
- Cupbearer does not own downstream business-task implementations.

## Simplicity Guardrails (Required)
- Keep one Fly app process with one SQLite DB for v1.
- Keep one worker loop in-process; do not introduce external queue infrastructure.
- Keep job handlers synchronous callables unless a concrete async need is proven.
- Keep job type routing explicit in code (no dynamic plugin loader/registry service).
- Keep external actions as explicit HTTP endpoint calls (`/v1/...`) with allowlists.

## Current Repo Map
- `seed.md`: original product intent and north-star scenario/personality notes.
- `plan-v1.md`: reduced MVP implementation sequence and definition of done.
- `architecture-v1.md`: agent-layer architecture/flow and risk audit.
- `tasks/`: legacy broad execution tasks (to be re-baselined to agent-layer scope).

## Implementation Order (MVP)
1. Foundation and runtime skeleton.
2. SQLite event/audit schema + migrations.
3. Twilio WhatsApp inbound/outbound integration.
4. Agent orchestration (Claude default + Codex stub adapter).
5. Persona/safety policy enforcement in one outbound path.
6. Endpoint action runner (auth/timeout/idempotency/retry).
7. mem0 memory integration + provenance.
8. E2E critical journeys as release gates.
9. Deployment hardening and production validation.

## TDD (E2E-First, Required)
- Default workflow is red -> green -> refactor using E2E tests for user-visible behavior.
- Start each feature by writing or updating an E2E scenario that fails for the intended behavior.
- Implement the minimum production code to make that E2E test pass.
- Refactor only after E2E is green and behavior is preserved.
- Do not treat a feature as complete without E2E coverage of its critical path.
- Unit tests are not the primary requirement in this repo; add them only for tight algorithmic logic or hard-to-isolate failure paths.

## E2E Coverage Baseline
- WhatsApp inbound webhook -> event persistence -> agent response.
- Retry/idempotency behavior under duplicate deliveries.
- External endpoint action execution with audit trail.
- Memory retrieval/injection and provenance persistence.
- Policy validator enforcement and confirmation gates.

## Definition of Done (Operational)
- Every outbound message/action is traceable to source events and policy pass.
- Duplicate deliveries do not create duplicate side effects.
- Restart/recovery preserves committed events and pending jobs.
- E2E release gates pass in CI and staging.

## Update Protocol For This File
- Update this file whenever architecture, task order, testing strategy, or integration boundaries change.
- Keep entries concise and decision-focused so new agents can grok the repo quickly.
