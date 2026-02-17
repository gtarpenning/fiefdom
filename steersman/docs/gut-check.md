# Gut Check

Use this before deeper implementation work to verify the current MVP server path is healthy.

## One-command run

```bash
./scripts/gut_check.sh --target local
```

This script:
- starts `steersman` on `127.0.0.1:8765`
- runs a small functional flow against infra and `/v1` endpoints
- verifies auth behavior and idempotency replay behavior
- shuts the server down

Run against an already-running server:

```bash
STEERSMAN_AUTH_TOKEN=my-token STEERSMAN_GUTCHECK_BASE_URL=http://127.0.0.1:8765 ./scripts/gut_check.sh --target remote
```

Supported env vars:
- `STEERSMAN_AUTH_TOKEN` (default: `test-token`)
- `STEERSMAN_HOST` (default: `127.0.0.1`)
- `STEERSMAN_PORT` (default: `8765`)
- `STEERSMAN_GUTCHECK_BASE_URL` (required for `--target remote`)
- `STEERSMAN_GUTCHECK_REMINDER_TITLE` (optional: create reminder in default list)
- `STEERSMAN_GUTCHECK_REMINDER_LIST` (optional override list for reminder create)
- `STEERSMAN_GUTCHECK_IMESSAGE_TO` (optional recipient for test iMessage send)
- `STEERSMAN_GUTCHECK_IMESSAGE_TEXT` (required with `...IMESSAGE_TO`)

## Optional manual skill checks

Create a reminder in the default list with your own text:

```bash
STEERSMAN_GUTCHECK_REMINDER_TITLE="Take out trash tonight" ./scripts/gut_check.sh --target local
```

Create in a specific list:

```bash
STEERSMAN_GUTCHECK_REMINDER_TITLE="Pay power bill" STEERSMAN_GUTCHECK_REMINDER_LIST="Personal" ./scripts/gut_check.sh --target local
```

Send a test iMessage:

```bash
STEERSMAN_GUTCHECK_IMESSAGE_TO="+14155550100" STEERSMAN_GUTCHECK_IMESSAGE_TEXT="steersman gut check" ./scripts/gut_check.sh --target local
```

## Manual run

You can also start the server directly:

```bash
STEERSMAN_AUTH_TOKEN=test-token python -m steersman serve --host 127.0.0.1 --port 8765
```

Then hit endpoints from another terminal with `curl`.
