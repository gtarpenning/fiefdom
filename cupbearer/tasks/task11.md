# Task 11: Deployment Hardening and MVP Done-Criteria Validation

## Objective
Validate production readiness for the reduced WhatsApp-first agent-layer MVP.

## Scope
- Deploy on Fly single app + single volume with health checks.
- Validate restart/recovery behavior for events and pending work.
- Validate idempotency under replay/failure drills.
- Validate policy and audit visibility in staging.
- Confirm E2E release gates and operational runbook completeness.

## Deliverables
- Deployment and operations runbook.
- Reliability validation notes (restart, replay, retry).
- MVP done-criteria checklist with evidence links.

## Acceptance Criteria
- Process restart does not lose committed event/audit data.
- Duplicate inbound delivery does not duplicate side effects.
- Outbound actions/messages are traceable to source event + policy decision.
- E2E gates are green before production release.
