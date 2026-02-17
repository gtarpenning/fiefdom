# Cupbearer Plan v1 (Agent-Layer MVP)

## 1) Product Focus (Locked)
Cupbearer is the **agent layer only** for a single user.  
It should not own business-task implementations (reminders, travel booking logic, notes internals, etc.).

Cupbearer is responsible for:
1. Receiving messages.
2. Running a high-quality agent loop with strong persona.
3. Calling external action endpoints.
4. Returning responses with traceability and safety checks.

## 2) Core Constraints
1. Single tenant only.
2. One Fly app process + one SQLite DB.
3. Event-first: immutable event log for inbound/outbound/actions.
4. Idempotent webhook processing and retriable outbound action calls.
5. Personality/safety policy checks are mandatory before outbound responses/actions.
6. Keep architecture simple; no extra queue infra, no dynamic plugin system.

## 3) Agent Requirements (Keep the Important Bits)
1. Tone contract (non-optional):
   - business casual
   - witty/playful/funny when appropriate
   - concise, on-topic, results-driven
2. Behavior contract:
   - asks clarifying questions when missing critical constraints
   - confirms before high-impact actions
   - explains tradeoffs clearly when presenting options
3. Intelligence contract:
   - use short-term thread context + long-term memory retrieval (mem0)
   - preserve memory provenance (what memory influenced response)
   - remain tool-competent without pretending capabilities

## 4) Runtime Strategy
1. Default runtime: **Claude agent loop**.
2. Keep a lightweight agent adapter interface so a `CodexAgent` stub can exist.
3. Cupbearer remains model/provider pluggable behind that interface.
4. No local task implementation logic: actions are HTTP endpoint calls to external repos/services.

## 5) Integration Boundary
1. Cupbearer calls remote actions as endpoint contracts, e.g.:
   - `POST /v1/reminders/create`
   - `POST /v1/notes/create`
   - `POST /v1/messages/send`
2. Each action contract must define:
   - auth method
   - timeout
   - idempotency key behavior
   - request/response schema
3. Cupbearer stores only audit metadata (`action_name`, `endpoint`, payload hash, result, latency, status).

## 6) Channel Choice for MVP
1. **MVP channel: Twilio WhatsApp (Sandbox first, production WhatsApp sender next).**
2. Reason:
   - fastest path to real phone chat loop
   - easy webhook model for FastAPI
   - consistent with later Twilio Voice add-on
3. Not chosen for MVP:
   - Google “SMS API” path (not a practical route for this use case)
   - Facebook Messenger first (more setup/review complexity for initial loop)

## 7) MVP User Journey
1. User sends WhatsApp message.
2. Cupbearer ingests + persists inbound event.
3. Agent retrieves context/memory.
4. Agent decides: respond directly or call one/more external endpoints.
5. Policy validator enforces persona + safety + action confirmation rules.
6. Cupbearer sends WhatsApp reply.
7. Cupbearer persists response event + action/memory provenance.

## 8) Build Order (Reduced)
1. Foundation:
   - FastAPI runtime
   - SQLite event/audit schema
   - health endpoint
2. Twilio WhatsApp transport:
   - inbound webhook
   - outbound message sender
   - webhook idempotency
3. Agent core:
   - Claude loop adapter
   - Codex stub adapter file
   - orchestrator (`ingest -> think -> optional action -> reply`)
4. Persona/policy enforcement:
   - enforce tone contract and high-impact confirmation gates
5. Endpoint tool/action runner:
   - explicit endpoint allowlist
   - auth, timeout, retry, idempotency key support
6. Memory:
   - mem0 `search` before response
   - mem0 `add` after response
   - provenance persisted per response event
7. E2E release gates:
   - inbound to outbound response
   - duplicate webhook idempotency
   - action call traceability
   - policy block/confirm path

## 9) Definition of Done (MVP)
1. You can chat with Cupbearer over WhatsApp end-to-end.
2. Responses consistently reflect the personality contract.
3. Cupbearer can call external action endpoints and report outcomes.
4. Duplicate webhook deliveries do not create duplicate side effects.
5. Every outbound response/action is traceable to source event + policy decision.
6. Restart/recovery preserves committed events and pending work.

## 10) Explicit Non-Goals (for MVP)
1. Implementing downstream business workflows inside Cupbearer.
2. Multi-channel expansion beyond WhatsApp-first (SMS/voice can be next).
3. Multi-tenant support.
4. Distributed architecture, extra queues, or plugin marketplaces.
