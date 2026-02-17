# Cupbearer Implementation Task List (Agent-Layer MVP)

1. `task1.md` - Foundation and runtime skeleton
2. `task2.md` - SQLite schema and migration layer (minimal audit model)
3. `task3.md` - Twilio WhatsApp transport (inbound/outbound + idempotency)
4. `task4.md` - Agent adapters (Claude default + Codex stub)
5. `task5.md` - Persona contract and policy enforcement
6. `task6.md` - Agent orchestration loop
7. `task7.md` - External endpoint action runner
8. `task8.md` - Memory integration via mem0 + provenance
9. `task9.md` - North-star conversation behavior (NYC planning as agent-layer scenario)
10. `task10.md` - E2E critical journeys and release gates
11. `task11.md` - Deployment hardening and MVP done-criteria validation

## Current Focus (Interface-First MVP)
- Completed foundations: task1-task3.
- Completed now: task4-task6 with minimal Claude wrapper and webhook->agent->policy->reply loop.
- Active now: task7 minimal Steersman action runner integration.
- Deferred as non-critical for first chat loop: task8-task9.

## Testing Priority
- E2E tests are the main quality signal for Cupbearer.
- Unit tests are optional and used only for isolated high-risk logic.
- A feature is not done until its critical user path is covered by E2E.
