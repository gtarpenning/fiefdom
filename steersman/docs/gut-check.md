# Gut Check

Use this before deeper implementation work to verify the current MVP server path is healthy.

## One-command run

```bash
./scripts/gut_check.sh
```

This script:
- starts `steersman` on `127.0.0.1:8765`
- runs a small functional flow against infra and `/v1` endpoints
- verifies auth behavior and idempotency replay behavior
- shuts the server down

## Optional overrides

```bash
STEERSMAN_AUTH_TOKEN=my-token STEERSMAN_PORT=9000 ./scripts/gut_check.sh
```

Supported env vars:
- `STEERSMAN_AUTH_TOKEN` (default: `test-token`)
- `STEERSMAN_HOST` (default: `127.0.0.1`)
- `STEERSMAN_PORT` (default: `8765`)

## Manual run

You can also start the server directly:

```bash
STEERSMAN_AUTH_TOKEN=test-token python -m steersman serve --host 127.0.0.1 --port 8765
```

Then hit endpoints from another terminal with `curl`.
