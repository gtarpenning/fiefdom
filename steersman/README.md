# steersman

Lib for turning your personal mac into a server. 

Goals: 
- expose macos features on a fastapi layer for agent consumption
- very portable, super lightweight, stateless?, ephemeral
- highly secure. multiple layers of protection. (port stuff, ip whitelisting, device macos whitelisting, security handshake, end to end encryption)
   - stretch: anomoly detection (separate repo) to shut off automatically if things don't feel right
- mac integrations: imessage, ical, apple notes, apple reminders, email, personal browser stuff (bookmarks, passwords, etc)
- other integrations: github, spotify, sonos, notion, obsidian, whatsapp

User flow:
- user installs and runs steersman from distributor (python? brew?)
- some sort of start command, probably launches a containerized deployment with access to disk? i want the lightest weight possible process, that can run in the background and serve traffic even when the user isn't using their computer (background stays on). On device! 
- comprehensive onboarding where the user logs into any services that need to be logged into (most of the apple ones we probably get for free)


Examples of integrations we should take:
- imessage: https://github.com/steipete/imsg 
- notes: https://clawhub.ai/steipete/apple-notes
- reminders: https://clawhub.ai/steipete/apple-reminders
- apple mail: https://mcpmarket.com/tools/skills/apple-mail-automation#automating-apple-mail-jxa-first-applescript-discovery
- apple health(?): https://mcpmarket.com/tools/skills/apple-health-fitness


Architecture: 
- single process fastapi service (launchd LaunchAgent?)
- stateless, with a config, keychain secrets, audit log
- security: mvp, only allow access over local network, zero external servicing. Agent process calls http://127.0.0.1:<port> (or http://localhost)
	•	Auth is not “trust localhost.” It’s:
	•	a unix-user-scoped secret stored in Keychain, or
- REST-ish endpoints; keep them predictable:
	•	/v1/skills/{skill}/...
	•	/v1/capabilities (what’s available)
Every endpoint returns:
	•	request_id
	•	audit_ref
	•	result or error

- integration backend management: 
	•	Native frameworks (PyObjC) for things like Calendar/Reminders (EventKit).
	•	JXA/AppleScript for Apple Mail and some UI-ish automation.
	•	SQLite reads for some apps (Messages DB) — but fragile across OS updates.
	•	“Bring your own tool” adapters: wrap proven repos as subprocess modules (your imessage example).

layout: 
steersman/
  steersman/
    __init__.py
    __main__.py          # python -m steersman (optional)
    cli.py               # Typer entrypoint (thin)
    app.py               # FastAPI app factory + router wiring
    server.py            # transport + lifecycle (UDS/TCP, launchd)
    config.py            # config schema + load/validate
    auth.py              # pairing, client identity, token mint/verify
    policy.py            # capability model + decision function (THE choke point)
    audit.py              # structured audit events + redaction
    models.py             # shared Pydantic schemas (requests/responses/events)
    skills/
      __init__.py         # skill registry + discovery
      imessage.py
      calendar.py
      notes.py
      reminders.py
      mail.py
      github.py
      spotify.py
      notion.py
  tests/
  pyproject.toml
  README.md


## Steersman architecture guidelines (principled + simple)

### North Star
- Keep the **trusted kernel** tiny and boring: auth, policy, audit, config, transport.
- Treat **skills as extensions**: easy to add/remove, never allowed to bypass the kernel.
- Prefer **declarative metadata** over ad-hoc wiring; generate UI/docs from it.

### Core abstractions (minimal set)
1) **RequestContext (`ctx`)**
- Created once per request (middleware) and injected into handlers.
- Contains: `request_id`, `principal` (caller identity), `config`, `policy`, `audit`.
- Rule: skills never reimplement auth/policy/audit; they only consume `ctx`.

2) **Capability model**
- Capabilities are stable strings: `"calendar.read"`, `"imessage.send"`, etc.
- Enforcement is centralized in `policy.py`:
  - `require(ctx, capability)` raises on deny
  - `check(ctx, capability)` returns bool
- Rule: capability checks are attached as route dependencies from manifest metadata (not manual handler calls).

3) **Skill interface = Router + Manifest**
- Each skill exports:
  - `manifest: SkillManifest` (single source of truth)
  - `router: APIRouter` (endpoints under `/v1/skills/{skill}/...`)
- `SkillManifest` includes: name/version, provided capabilities, operation->capability mapping, optional risk flags/requirements/health checks.
- Rule: `/v1/capabilities`, onboarding prompts, and docs grouping are derived from manifests (no duplicated lists).

### “Gorgeous” interface layer (generate, don’t hand-author)
- Use FastAPI docs (Swagger/ReDoc) with clean tags per skill.
- Auth scope is default-deny for `/v1/*`; only explicitly allowlisted infra endpoints are unauthenticated (e.g. `/healthz`, pairing bootstrap).
- Provide catalog endpoints driven by manifests:
  - `GET /v1/skills` (installed/enabled + status)
  - `GET /v1/skills/{skill}/health` + `/requirements`
- Add a simple `GET /` landing page linking to `/docs`, `/redoc`, and showing enabled skills + missing permissions.

### Uniform response + errors (DRY)
- Action JSON endpoints return an envelope:
  - `request_id`, `audit_ref`, and `result` OR `error`
- Infra endpoints (`/`, `/healthz`, docs) can return plain HTTP responses.
- Use one exception handler with a small stable error taxonomy:
  - `auth_denied`, `invalid_input`, `dependency_unavailable`, `internal`
  - include `retryable: true|false` in error payloads.

### Idempotency for mutating actions
- All mutating endpoints (send/create/update/delete) require `Idempotency-Key`.
- The server deduplicates by `(principal, route, key)` within a bounded TTL window.

### Transport/security posture (local-only first)
- Default mode is **local-only**:
  - bind to `127.0.0.1` and `::1` (or later: Unix socket)
  - refuse startup if not loopback
- Auth is not “trust localhost”:
  - use a per-user secret in Keychain and/or client identity bootstrap.
- Audit everything:
  - capability, principal, timestamp, outcome, redacted metadata.

### Integration backends (keep utilities, not frameworks)
- Share small helpers (e.g., AppleScript runner, subprocess wrapper, EventKit helper).
- Avoid grand “backend architecture”; skills own their integration logic and only rely on kernel services via `ctx`.

### Dependency rules (keep it auditable)
- `app.py` is the only entry that attaches `principal` and `ctx`.
- `skills/*` may import `models`, `policy.require/check`, and `audit.emit` via `ctx`—but must not mint tokens or bypass auth.
- Kernel code should not import skill modules except through a registry/discovery function.
