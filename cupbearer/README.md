# Cupbearer

Cupbearer is a single-tenant personal assistant service.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
make dev-install
cp .env.example .env
export $(grep -v '^#' .env | xargs)
```

## Run

```bash
make run
```

## Database

```bash
make migrate
make seed
```

## E2E Tests

```bash
make test-e2e
```

E2E tests are the primary quality gate for this repository.

Live Twilio credential smoke test (runs only when explicitly enabled):

```bash
CUPBEARER_RUN_LIVE_TWILIO_TESTS=1 python -m pytest -m twilio_live tests/e2e/test_twilio_live_smoke.py
```

## Task 3 Runtime Surface

- `POST /ingest/events`: append inbound/outbound immutable events (idempotent via `X-Idempotency-Key`).
- `POST /jobs`: enqueue durable jobs (idempotent via `X-Idempotency-Key`).
- `GET /jobs/{job_id}`: inspect current job status (`pending`, `running`, `retry`, `succeeded`, `dead_letter`).
- `POST /channels/twilio/whatsapp/webhook`: ingest Twilio WhatsApp inbound webhook (signature-validated, idempotent by `MessageSid`).
- `POST /channels/whatsapp/send`: send outbound WhatsApp message through Twilio API (idempotent via `X-Idempotency-Key`).
- Event `direction` is validated (`inbound` or `outbound`).
- Job `type` must match explicitly supported worker handlers (currently `noop`, `test.fail_always`).
