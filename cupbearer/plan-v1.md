# Cupbearer Plan v1

## 1) Single Strategy (No Branches)
Build one Python monolith on one Fly.io VM with one SQLite database, one background worker loop, and one agent runtime.  
Messages/jobs/skills/audit logs are stored locally in that VM, while long-term memory is delegated to `mem0` and linked back to local events.

This is the simplest path that still supports growth.

## 2) Hard Product Rules
1. Single tenant only (you).
2. Event-driven: every inbound/outbound interaction is an immutable event.
3. Idempotent integrations: every webhook and job can be retried safely.
4. Model-agnostic via LiteLLM only.
5. Assistant persona is enforced by policy, not left to prompt luck.
6. Skills are versioned and executable with explicit permissions.
7. No distributed systems until proven necessary.

## 3) Core Architecture
1. Runtime: Python 3.12 + FastAPI + Uvicorn.
2. Storage: SQLite (WAL mode) with:
   - `events` (append-only source of truth)
   - `jobs` (durable queue with retries/backoff)
   - `contacts`, `threads`, `messages`
   - `skills`, `skill_versions`, `skill_runs`
   - `auth_accounts`, `oauth_tokens`
3. Memory layer:
   - Use `mem0` as the primary long-term memory abstraction (search/add/dedup/update flows).
   - Keep lightweight local metadata in SQLite for observability and traceability (memory references tied to `event_id`).
4. Search:
   - SQLite FTS5 for conversation/history retrieval.
   - Use `mem0` retrieval APIs for semantic recall instead of custom embedding plumbing in v1.
5. Agent:
   - One orchestrator loop: `ingest -> classify intent -> retrieve context -> plan -> execute skills/tools -> draft response -> policy check -> send`.
6. Integrations (first wave):
   - Google OAuth + Calendar/Gmail read/write scopes you approve.
   - Slack user token (single workspace + DMs/channels you allow).
   - Twilio SMS + voice.
   - WhatsApp via Twilio or Meta Cloud API (pick one first; Twilio is simpler if already using it).
7. External action service integration:
   - Device-native actions (`imessage`, `notes`, future local automations) are hosted by an external service (`../steersman`).
   - Cupbearer only calls approved REST endpoints with auth, timeout, and idempotency guarantees.
   - Cupbearer does not own/process-host this runtime.
8. Deployment:
   - Single Fly app, single volume, health checks, nightly DB backup to object storage.

## 4) Persona and Safety Enforcement
1. Define a strict `assistant_contract`:
   - tone: business casual, witty/playful, concise, results-driven
   - never off-topic for critical tasks
   - must confirm before high-impact actions
2. Add output policy validator before send:
   - style check (tone/length)
   - safety check (sensitive actions)
   - action check (did it actually answer the request)
3. Add escalation behavior:
   - when uncertain, ask clarifying question
   - when blocked, summarize options with recommendation

## 5) Memory System via `mem0`
1. Capture and retrieval contract:
   - use `memory.search(query=message, user_id, limit=3)` before response generation
   - use `memory.add(messages, user_id)` after assistant response
2. Interaction pattern:
   - implement a `chat_with_memories(message, user_id)` wrapper around LLM calls
   - system prompt includes retrieved memory bullet points
3. Storage responsibilities:
   - `mem0` owns semantic memory extraction, indexing, deduplication, and long-term recall mechanics
   - Cupbearer SQLite keeps event log + references for traceability and debugging
4. Explainability:
   - persist which returned memory IDs/snippets were injected into the prompt for each reply event
5. Guardrails:
   - per-user namespace (`user_id`) is mandatory
   - enforce maximum memory payload in prompt to control latency/cost

## 6) Skills System v1
1. Skill package format:
   - `skill.yaml` (name, version, inputs, permissions)
   - executable entrypoint (Python function or script)
2. Versioning:
   - immutable `skill_versions` records
   - active version pointer per skill
3. Execution:
   - run through a skill runner with timeout, stdout/stderr capture, structured result.
4. Permissions:
   - each skill declares allowed tools (calendar, messaging, web, files).
   - deny by default.
5. Rollback:
   - one command to revert active skill version.
6. Remote skills/actions:
   - support HTTP-executed actions through external REST endpoints (served by `../steersman`)
   - each remote action endpoint must declare auth, timeout, input schema, and idempotency behavior
   - map remote actions into the same `skill_runs` audit trail as local skills
7. Invocation model (decision point):
   - default path: wrap REST calls as skills so all execution goes through one permissioned skill runner
   - optional path: expose some REST calls as first-class tools if lower latency/direct routing is needed
   - pick one default for v1 and keep the other as a later optimization

## 7) North Star Workflow (NYC Trip)
Build this as the first end-to-end scenario and treat it as the acceptance test.

1. Input: “Plan NYC trip with friends.”
2. Assistant asks for constraints (dates, budget, must-see, who to include).
3. Assistant messages friends via approved channels, tracks replies, nudges non-responders.
4. Assistant summarizes availability/preferences.
5. Assistant generates itinerary options with tradeoffs.
6. Assistant calls you (Twilio voice) with concise briefing.
7. Assistant sends final plan + action checklist.

## 8) Build Order (Most Reliable Path)
1. Foundation (Week 1)
   - FastAPI app, SQLite schema, event log, jobs table, health checks, backup job.
2. Messaging + Identity (Week 2-3)
   - Twilio SMS inbound/outbound, Google OAuth, Slack connector.
3. Agent Core (Week 3-4)
   - LiteLLM abstraction, orchestrator loop, policy validator, audit logs.
4. Memory + Retrieval (Week 4-5)
   - `mem0` integration (`search` + `add` flow), memory citations, local metadata logging.
5. Skills v1 (Week 5-6)
   - skill spec, versioning, runner, permission gates.
6. External Actions Integration (Week 6)
   - integrate Cupbearer with `../steersman` REST endpoints for `imessage` + `notes`, including auth handshake, endpoint contracts, retries/timeouts.
7. North Star Implementation (Week 6-7)
   - NYC workflow skill + multi-contact coordination + voice briefing.
8. Hardening (Week 7-8)
   - retry/idempotency audit, load tests, failure drills, backup restore test.

## 9) Definition of Done (Bulletproof Criteria)
1. A killed/restarted VM does not lose committed events or jobs.
2. Duplicate webhook deliveries do not create duplicate side effects.
3. Every outbound action is traceable to a user request + policy pass.
4. North star trip workflow succeeds end-to-end in staging and production.
5. Backup restore drill completes successfully.
6. Persona compliance rate is high on test set (target: >=95%).
7. No P0/P1 issues in 7-day soak run.

## 10) What Not To Build Yet
1. Multi-tenant support.
2. Kubernetes/microservices.
3. Complex workflow engines.
4. Premature plugin marketplaces.
5. Multiple databases.

## 11) Immediate Next Actions
1. Lock API/provider choices:
   - Twilio for SMS+voice.
   - Twilio WhatsApp or Meta WhatsApp Cloud (choose one now).
2. Create schema + migrations from sections 3/6 (do not build custom memory tables beyond references/observability).
3. Implement `mem0`-backed `chat_with_memories(...)` flow and wire it into the orchestrator.
4. Integrate with `../steersman` endpoints for first remote actions: `imessage.send`, `notes.create`.
5. Choose v1 invocation default: REST-as-skill wrapper (recommended) vs direct tool adapter.
6. Implement event ingestion + durable jobs loop first.
7. Add the NYC workflow as the first real integration test.
