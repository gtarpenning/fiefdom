# Task 1: Foundation and Runtime Skeleton

## Objective
Establish a minimal, production-ready baseline for the Cupbearer agent-layer monolith.

## Scope
- Keep Python 3.12 + FastAPI + Uvicorn runtime skeleton.
- Finalize config management and startup validation for required env vars.
- Keep health/readiness endpoints for Fly deployment.
- Keep clear module boundaries for transport, agent, policy, actions, memory, and persistence.
- Keep structured logging with request/event correlation IDs.
- Keep E2E test scaffold for app boot and health checks.

## Deliverables
- Running API service with health endpoints.
- Config and logging baseline.
- E2E baseline for service boot.
- Local run instructions aligned to MVP scope.

## Acceptance Criteria
- Service boots locally and responds on health endpoints.
- Missing required env vars fail startup.
- Logs include stable correlation identifiers.
- Baseline E2E test passes locally and in CI.
