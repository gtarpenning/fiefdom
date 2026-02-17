# Task 4: Agent Adapters (Claude Default + Codex Stub)

## Objective
Create a stable agent interface with Claude as default runtime and Codex as a non-blocking stub.

## Scope
- Define agent adapter interface (single turn contract).
- Implement a minimal Claude adapter wrapper for single-turn text generation.
- Add Codex stub adapter file and wiring path for future swap/testing.
- Keep provider/model config externalized to environment.
- Keep adapter output structured for orchestrator + policy checks.

## Deliverables
- `AgentAdapter` interface.
- Claude adapter implementation (simple prompt wrapper, no tool calls in v0).
- Codex stub adapter and registration mechanism.

## Acceptance Criteria
- Runtime uses Claude adapter by default.
- Adapter can be switched by config without touching orchestrator logic.
- Stub path compiles/loads cleanly even if not production-enabled.

## Deferred (Post-MVP)
- Structured tool intent output.
- Multi-message context packing beyond latest message.
