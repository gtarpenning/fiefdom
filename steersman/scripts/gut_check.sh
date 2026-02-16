#!/usr/bin/env bash
set -euo pipefail

HOST="${STEERSMAN_HOST:-127.0.0.1}"
PORT="${STEERSMAN_PORT:-8765}"
TOKEN="${STEERSMAN_AUTH_TOKEN:-test-token}"
BASE_URL="http://${HOST}:${PORT}"

if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: curl is required for gut check" >&2
  exit 1
fi

SERVER_LOG="$(mktemp -t steersman-gut-check.XXXXXX.log)"

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]] && kill -0 "${SERVER_PID}" >/dev/null 2>&1; then
    kill "${SERVER_PID}" >/dev/null 2>&1 || true
    wait "${SERVER_PID}" >/dev/null 2>&1 || true
  fi
  rm -f "${SERVER_LOG}"
}
trap cleanup EXIT

STEERSMAN_AUTH_TOKEN="${TOKEN}" \
python -m steersman serve --host "${HOST}" --port "${PORT}" >"${SERVER_LOG}" 2>&1 &
SERVER_PID=$!

for _ in $(seq 1 80); do
  if curl -fsS "${BASE_URL}/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done

if ! curl -fsS "${BASE_URL}/healthz" >/dev/null 2>&1; then
  echo "ERROR: server did not become healthy" >&2
  echo "--- server log ---" >&2
  cat "${SERVER_LOG}" >&2
  exit 1
fi

request() {
  local method=$1
  local path=$2
  local expected_status=$3
  local body=${4:-}
  shift 4 || true
  local -a curl_args
  curl_args=(-sS -X "${method}" "${BASE_URL}${path}" -H "Accept: application/json")
  for header in "$@"; do
    curl_args+=("${header}")
  done
  if [[ -n "${body}" ]]; then
    curl_args+=(-H "Content-Type: application/json" -d "${body}")
  fi
  curl_args+=(-w $'\n%{http_code}')

  local out http body_out
  out=$(curl "${curl_args[@]}")
  http=$(printf '%s\n' "${out}" | tail -n1)
  body_out=$(printf '%s\n' "${out}" | sed '$d')

  printf '[%s %s] status=%s expected=%s\n' "${method}" "${path}" "${http}" "${expected_status}"
  printf '%s\n\n' "${body_out}"

  if [[ "${http}" != "${expected_status}" ]]; then
    echo "ERROR: unexpected status for ${method} ${path}" >&2
    exit 1
  fi
}

echo "Running Steersman gut check against ${BASE_URL}"

request GET /healthz 200 ""
request GET / 200 ""
request GET /v1/ping 401 ""
request GET /v1/ping 200 "" -H "X-Steersman-Token: ${TOKEN}"
request GET /v1/skills 200 "" -H "X-Steersman-Token: ${TOKEN}"
request GET /v1/reminders 200 "" -H "X-Steersman-Token: ${TOKEN}"
request POST /v1/notes 400 '{"text":"buy milk"}' -H "X-Steersman-Token: ${TOKEN}"
request POST /v1/notes 201 '{"text":"buy milk"}' -H "X-Steersman-Token: ${TOKEN}" -H 'Idempotency-Key: gut-check-1'
request POST /v1/notes 201 '{"text":"buy milk"}' -H "X-Steersman-Token: ${TOKEN}" -H 'Idempotency-Key: gut-check-1'

echo "Gut check passed"
