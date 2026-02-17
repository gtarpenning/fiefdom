# Fiefdom Demo: Full System Walkthrough

End-to-end setup for the Steersman + Cupbearer personal assistant stack.

## Architecture Overview

```
Phone (WhatsApp)
    │
    ▼
Twilio ──webhook──▶ ngrok tunnel ──▶ Cupbearer (:8000)
                                        │
                                        ├─▶ Claude API (agent reasoning)
                                        ├─▶ Twilio API (reply to user)
                                        └─▶ Steersman (:8765, loopback)
                                               ├─▶ remindctl (Reminders.app)
                                               └─▶ imsg (iMessage)
```

**Cupbearer** receives WhatsApp messages via Twilio webhook, runs them through
Claude for reasoning, and sends replies back. It uses an event-sourced SQLite
store with a durable job queue for reliability.

**Steersman** is a local-only FastAPI server that wraps macOS capabilities
(Reminders, iMessage) behind authenticated REST endpoints with audit logging.

---

## Prerequisites

| Dependency | Install |
|---|---|
| Python 3.11+ | `brew install python@3.12` |
| ngrok | `brew install ngrok` |
| remindctl | `brew install steipete/tap/remindctl` |
| imsg | Download from https://github.com/steipete/imsg |
| Twilio account | https://www.twilio.com (WhatsApp sandbox or production) |
| Anthropic API key | https://console.anthropic.com |

Grant macOS permissions when prompted: Reminders access, Contacts, Full Disk
Access (for Messages DB if using imsg).

---

## Step 1: Start Steersman

```bash
cd fiefdom/steersman

# Install
python -m pip install -e '.[dev]'

# Set auth token (or export in shell)
export STEERSMAN_AUTH_TOKEN=dev-token

# Start (foreground)
python -m steersman serve --host 127.0.0.1 --port 8765

# Or install as background LaunchAgent
python -m steersman start --launchd
```

### Verify Steersman

```bash
# Health check
curl http://127.0.0.1:8765/healthz
# → {"status":"ok"}

# Authenticated ping
curl -H "X-Steersman-Token: dev-token" http://127.0.0.1:8765/v1/ping
# → {"request_id":"...","result":{"message":"pong"}}

# List skills
curl -H "X-Steersman-Token: dev-token" http://127.0.0.1:8765/v1/skills
```

### Test Reminders

```bash
curl -X POST http://127.0.0.1:8765/v1/reminders \
  -H "X-Steersman-Token: dev-token" \
  -H "Idempotency-Key: demo-reminder-1" \
  -H "Content-Type: application/json" \
  -d '{"title":"Demo reminder from Fiefdom","list":"steersman"}'
```

Open Reminders.app and check the "steersman" list.

### Test iMessage

```bash
curl -X POST http://127.0.0.1:8765/v1/imessage/send \
  -H "X-Steersman-Token: dev-token" \
  -H "Idempotency-Key: demo-imsg-1" \
  -H "Content-Type: application/json" \
  -d '{"to":"+1YOURNUMBER","text":"Hello from Fiefdom","service":"auto"}'
```

---

## Step 2: Start Cupbearer

```bash
cd fiefdom/cupbearer

# Install
make dev-install

# Copy and fill in env
cp .env.example .env
# Edit .env:
#   ANTHROPIC_API_KEY=sk-ant-...
#   TWILIO_ACCOUNT_SID=AC...
#   TWILIO_AUTH_TOKEN=...
#   TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
#   CUPBEARER_TWILIO_SEND_MODE=live

# Run migrations
make migrate

# Start server
make run
# → uvicorn on 0.0.0.0:8000
```

### Verify Cupbearer

```bash
curl http://localhost:8000/health/live
# → {"status":"ok"}

curl http://localhost:8000/health/ready
# → {"status":"ok"}
```

---

## Step 3: Expose Cupbearer via ngrok

```bash
ngrok http 8000
```

Copy the HTTPS forwarding URL (e.g., `https://abc123.ngrok-free.app`).

---

## Step 4: Configure Twilio Webhook

1. Go to [Twilio Console](https://console.twilio.com)
2. Navigate to **Messaging > Try it out > Send a WhatsApp message** (sandbox)
   - Or your production WhatsApp sender configuration
3. Set the webhook URL:
   ```
   https://abc123.ngrok-free.app/channels/twilio/whatsapp/webhook
   ```
   Method: **POST**
4. Save

### Join the Twilio Sandbox (if using sandbox)

Send the join code from your phone to the Twilio sandbox WhatsApp number.
The code looks like `join <word>-<word>`.

---

## Step 5: Send a Message

1. Open WhatsApp on your phone
2. Send a message to the Twilio WhatsApp number
3. Watch the flow:
   - ngrok forwards to Cupbearer
   - Cupbearer logs the inbound event, enqueues an `agent.turn` job
   - Worker picks up the job, calls Claude API
   - Claude's reply is policy-checked and sent back via Twilio
   - You receive the reply in WhatsApp

### Monitor

```bash
# Cupbearer logs in the terminal running `make run`

# Check job status
curl http://localhost:8000/jobs/<job_id>

# Steersman audit log
tail -f steersman/.steersman/audit.jsonl | python -m json.tool
```

---

## Step 6: Test Steersman Integration (Manual)

Cupbearer doesn't yet call Steersman automatically during agent turns (the
orchestrator currently only does Claude -> reply). To test the full path
manually:

```bash
# Create a reminder via Cupbearer -> Steersman
curl -X POST http://127.0.0.1:8765/v1/reminders \
  -H "X-Steersman-Token: dev-token" \
  -H "Idempotency-Key: demo-$(uuidgen)" \
  -H "Content-Type: application/json" \
  -d '{"title":"Buy groceries","list":"steersman","due":"tomorrow"}'

# Send an iMessage via Steersman
curl -X POST http://127.0.0.1:8765/v1/imessage/send \
  -H "X-Steersman-Token: dev-token" \
  -H "Idempotency-Key: demo-$(uuidgen)" \
  -H "Content-Type: application/json" \
  -d '{"to":"+1YOURNUMBER","text":"Sent via Fiefdom agent stack"}'
```

---

## Full Startup Checklist

```
Terminal 1:  cd steersman && python -m steersman serve
Terminal 2:  cd cupbearer && make run
Terminal 3:  ngrok http 8000
Then:        Configure Twilio webhook with ngrok URL
Then:        Send WhatsApp message from phone
```

---

## Teardown

```bash
# Stop Cupbearer: Ctrl+C in terminal 2
# Stop ngrok: Ctrl+C in terminal 3
# Stop Steersman:
python -m steersman stop --launchd   # if using launchd
# or Ctrl+C in terminal 1
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Steersman 403 | Check `X-Steersman-Token` matches `STEERSMAN_AUTH_TOKEN` |
| Twilio signature validation fails | Ensure ngrok URL in Twilio console matches exactly; set `CUPBEARER_TWILIO_VALIDATE_SIGNATURE=0` temporarily to debug |
| `remindctl` not found | `brew install steipete/tap/remindctl` and grant Reminders permission |
| `imsg` not found | Install from GitHub, ensure it's on PATH |
| Claude API errors | Check `ANTHROPIC_API_KEY` is set and valid |
| ngrok URL changed | Update Twilio webhook URL (ngrok free tier rotates URLs) |
| Job stuck in `running` | Worker crashed mid-job; restart Cupbearer, job will retry |
| WhatsApp reply not received | Check `CUPBEARER_TWILIO_SEND_MODE=live` (not `mock`) |

---

## Recommendations for Improvement

### High Priority

**1. Give Claude tools (Steersman as function calls)**

The agent adapter currently does a single Claude API call with no tools. Claude
can't actually use Steersman capabilities (reminders, iMessage) autonomously.
Wire up Steersman endpoints as Claude tool definitions so the agent can decide
to create reminders or send messages during a conversation turn.

```python
# In agent.py, add tools to the Claude API payload:
"tools": [
    {
        "name": "create_reminder",
        "description": "Create a reminder in Apple Reminders",
        "input_schema": { ... }
    },
    {
        "name": "send_imessage",
        "description": "Send an iMessage to a contact",
        "input_schema": { ... }
    }
]
```

Then handle `tool_use` content blocks in the response by calling Steersman and
feeding results back as `tool_result` messages in a multi-turn loop.

**2. Conversation history / memory**

The Claude adapter sends a single user message with no history. Each turn is
stateless. Add conversation context by:
- Loading recent messages from the `messages` table for the thread
- Passing them as prior messages in the Claude API call
- This is the difference between a chatbot and an assistant

**3. Replace ngrok with a persistent tunnel or reverse proxy**

ngrok free tier gives you a random URL that changes on every restart, requiring
you to update Twilio every time. Options:
- **ngrok paid plan**: stable subdomain (`yourname.ngrok.io`)
- **Cloudflare Tunnel**: free, stable hostname, no port exposure
- **Tailscale Funnel**: if you use Tailscale already, zero config
- **Deploy Cupbearer to a VPS**: $5/mo Hetzner/Fly.io, no tunnel needed

**4. Single startup script / process manager**

Running 3 terminals is fragile. Options:
- **Makefile at project root**: `make up` starts both services + ngrok
- **`honcho` / `foreman`** with a `Procfile`:
  ```
  steersman: python -m steersman serve
  cupbearer: cd cupbearer && uvicorn cupbearer.main:app --host 0.0.0.0 --port 8000
  ngrok: ngrok http 8000
  ```
- **Docker Compose**: if you want isolation (but macOS integrations make this
  tricky for Steersman)

### Medium Priority

**5. Webhook signature validation + replay protection**

Cupbearer validates Twilio signatures (good), but there's no timestamp check.
Twilio includes a timestamp you can use to reject stale webhooks (> 5 min old).

**6. Health check that verifies downstream dependencies**

`/health/ready` only checks if the app initialized. It should also verify:
- SQLite is accessible
- Claude API key is valid (cached check)
- Steersman is reachable (if integrated)
- Worker is running

**7. Structured logging**

Both services print to stdout. Use structured JSON logging (e.g., `structlog`)
so you can pipe to a log aggregator or just `jq` filter locally.

**8. Rate limiting on webhook endpoint**

No rate limiting on `/channels/twilio/whatsapp/webhook`. A misbehaving Twilio
retry loop or someone probing the endpoint could overwhelm the worker queue.

**9. Auto-migration on startup**

Cupbearer runs migrations via `make migrate` (separate step). The lifespan
already calls `apply_pending_migrations()` - verify this works reliably so
`make migrate` is only needed for manual/debugging use.

### Lower Priority

**10. Agent adapter: use the Anthropic SDK instead of raw urllib**

The Claude adapter uses `urllib.request` directly. The official
`anthropic` Python SDK handles retries, streaming, tool use parsing, and
error handling out of the box. It would simplify the adapter significantly.

**11. WhatsApp media support**

Currently only handles text messages. Twilio webhooks include `MediaUrl0`,
`MediaContentType0` etc. for images/audio. Supporting these (even just
forwarding to Claude as images) would make the assistant more useful.

**12. Observability**

Add OpenTelemetry traces or at minimum request-id propagation between
Cupbearer and Steersman so you can trace a WhatsApp message through the
entire system.

**13. Test the full integration path end-to-end**

The e2e tests for each service exist independently. Add a test that exercises
the full Twilio webhook -> Cupbearer -> Claude (mocked) -> Twilio reply path
with Steersman tool calls included.
