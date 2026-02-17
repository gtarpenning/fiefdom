# Task 2: SQLite Schema and Migration Layer (Minimal)

## Objective
Implement the minimal durable data model needed for an audited agent loop.

## Scope
- Keep SQLite WAL mode and pragmatic durability settings.
- Create/adjust migrations for:
  - `events` (immutable inbound/outbound source of truth)
  - `action_audit` (endpoint calls, retries, latency, status)
  - `policy_audit` (policy decision and reason codes)
  - `memory_provenance` (retrieved memory linked to response event)
  - optional lightweight `threads/messages` metadata if needed for routing
- Keep explicit repository transaction boundaries.

## Deliverables
- Migration scripts + migration runner.
- Repository interfaces for event and audit writes.
- Seed/bootstrap script for local development.

## Acceptance Criteria
- Fresh DB creation from zero migrations succeeds.
- Migration re-runs are idempotent.
- Event records are immutable in write paths.
