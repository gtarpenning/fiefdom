# AGENTS.md

Purpose: keep implementation simple, secure, and auditable.

## Engineering Rules
- Build the smallest thing that satisfies the current phase.
- Prefer explicit contracts over implicit behavior.
- Keep the trusted kernel small: transport, auth, policy, audit, config.
- Skills are extensions; they must not bypass kernel controls.
- Default deny for `/v1/*`; explicitly allowlist unauthenticated infra endpoints only.

## Interface Rules
- Capability checks are attached at routing/dependency layer from manifest metadata.
- Action JSON endpoints use the standard envelope (`request_id`, `audit_ref`, `result|error`).
- Infra endpoints (`/`, `/healthz`, docs) can return plain HTTP responses.
- Mutating endpoints require `Idempotency-Key`.

## Error Rules
- Use one handler with stable error kinds:
  - `auth_denied`
  - `invalid_input`
  - `dependency_unavailable`
  - `internal`
- Include `retryable` in error payloads.

## Execution Rules
- Ship in thin vertical slices.
- Use TDD for all feature work: write a failing functional E2E test first, then implement until it passes.
- Generate at least one native end-to-end test per added feature/path.
- Prefer functional E2E tests only; avoid unit-test-only coverage.
- Do not add new abstractions unless at least two callers need them.
