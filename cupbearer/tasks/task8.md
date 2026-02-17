# Task 8: Memory Integration via mem0 + Provenance

## Objective
Add long-term memory recall while preserving explainability and prompt discipline.

## Scope
- Retrieve memory before generation via mem0 search APIs.
- Inject bounded memory context into agent input.
- Write back salient conversation memory after response.
- Persist memory provenance records linked to outbound events.
- Keep single-user namespace boundaries explicit.

## Deliverables
- mem0 client integration.
- Memory retrieval/writeback orchestration hooks.
- Provenance persistence in `memory_provenance`.

## Acceptance Criteria
- Retrieved memory is used in generation pipeline when available.
- Memory IDs/snippets used for a response are auditable.
- Memory payload limits are enforced to control latency/cost.
