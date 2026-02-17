# Task 10: E2E Critical Journeys and Release Gates

## Objective
Use E2E tests as the primary release gate for the agent-layer MVP.

## Scope
- Define critical E2E journeys:
  - WhatsApp inbound -> event persistence -> agent response
  - duplicate delivery idempotency behavior
  - external endpoint action execution + audit trace
  - policy validator pass/fail + confirmation gate
  - memory retrieval/injection + provenance logging
  - NYC scenario conversation behavior
- Build deterministic fixtures/provider doubles where needed.
- Wire required E2E suites into CI gate.

## Deliverables
- E2E suite covering all critical journeys.
- CI configuration that blocks release on E2E failures.
- Local/staging E2E runbook.

## Acceptance Criteria
- Critical journeys pass in CI and staging.
- Failing E2E blocks release.
- Idempotency and policy guarantees are verified by E2E, not only unit tests.
