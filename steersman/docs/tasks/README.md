# Implementation Tasks (Ordered)

Objective: deliver a minimal, secure, robust local-first interface layer.

## Phase 0 - Bootstrap
1. Create package skeleton (`steersman/`, `tests/`, `pyproject.toml`) and basic app entrypoints.
2. Create E2E test run structure first (`tests/e2e/`, test app launcher, fixtures, one happy-path smoke test).
3. Add `config.py` with strict schema and loopback-only defaults.
4. Add `server.py` startup guard that refuses non-loopback bind.
5. Add `/healthz` endpoint and one functional E2E assertion through the real app boundary.

## Phase 1 - Trusted Kernel
6. Implement request context middleware (`request_id`, `principal`, `audit_ref`).
7. Implement auth bootstrap + per-user Keychain secret verification.
8. Implement policy engine with capability primitives (`require`, `check`).
9. Implement structured audit logging with redaction.
10. Add functional E2E tests for auth deny/allow, policy deny/allow, and audit emission.

## Phase 2 - Interface Contract
11. Define shared Pydantic models for envelope and error payload.
12. Implement global exception handler with error kinds + `retryable`.
13. Apply envelope only to action JSON endpoints; keep infra endpoints plain.
14. Add idempotency middleware/storage for mutating routes (`Idempotency-Key`).
15. Add functional E2E tests for envelope shape, error mapping, and idempotency replay behavior.

## Phase 3 - Skill System
16. Implement skill registry/discovery and `SkillManifest` model.
17. Require operation->capability mapping in manifests.
18. Attach capability checks as route dependencies from manifest metadata.
19. Implement catalog endpoints: `GET /v1/skills`, `GET /v1/skills/{skill}/health`, `GET /v1/skills/{skill}/requirements`.
20. Add functional E2E tests that prove no skill route can execute without mapped capability.

## Phase 4 - First Vertical Skills
21. Ship one low-risk read-only skill (calendar or reminders read).
22. Ship one mutating skill (e.g. reminders create) using idempotency.
23. Add functional E2E contract tests for both skills (auth, policy, audit, envelope).
24. Add docs examples for request/response and failure cases.

## Phase 5 - Packaging and Ops
25. Add CLI (`steersman start/status/doctor`) with minimal flags.
26. Add launchd integration for background startup.
27. Add installer path (pipx/brew decision) and onboarding flow.
28. Add operational docs for logs, key rotation, and safe recovery.

## Exit Criteria (v1)
29. All `/v1/*` endpoints are authenticated by default.
30. All mutating endpoints enforce idempotency.
31. At least two skills run through the same kernel controls with full functional E2E coverage.
