#!/usr/bin/env bash
set -euo pipefail

TARGET="local"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --target requires one value: local|remote" >&2
        exit 1
      fi
      TARGET="$2"
      shift 2
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      echo "Usage: ./scripts/gut_check.sh [--target local|remote]" >&2
      exit 1
      ;;
  esac
done

if [[ "${TARGET}" != "local" && "${TARGET}" != "remote" ]]; then
  echo "ERROR: --target must be one of: local, remote" >&2
  exit 1
fi

HOST="${STEERSMAN_HOST:-127.0.0.1}"
PORT="${STEERSMAN_PORT:-8765}"
TOKEN="${STEERSMAN_AUTH_TOKEN:-test-token}"
REMOTE_BASE_URL="${STEERSMAN_GUTCHECK_BASE_URL:-}"
REMINDER_TITLE="new note: $(date '+%Y-%m-%d %H:%M:%S')"
REMINDER_LIST="steersman"
IMESSAGE_TO="14152358265"
IMESSAGE_TEXT="hello friend, griffin just ran a test of his imessage skill. HA NERD"

if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: curl is required for gut check" >&2
  exit 1
fi

BASE_URL=""
if [[ "${TARGET}" == "local" ]]; then
  BASE_URL="http://${HOST}:${PORT}"
else
  if [[ -z "${REMOTE_BASE_URL}" ]]; then
    echo "ERROR: STEERSMAN_GUTCHECK_BASE_URL is required for --target remote" >&2
    exit 1
  fi
  BASE_URL="${REMOTE_BASE_URL}"
fi

SERVER_LOG=""
cleanup() {
  if [[ -n "${SERVER_PID:-}" ]] && kill -0 "${SERVER_PID}" >/dev/null 2>&1; then
    kill "${SERVER_PID}" >/dev/null 2>&1 || true
    wait "${SERVER_PID}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${SERVER_LOG}" ]]; then
    rm -f "${SERVER_LOG}"
  fi
}
trap cleanup EXIT

if [[ "${TARGET}" == "local" ]]; then
  SERVER_LOG="$(mktemp -t steersman-gut-check.XXXXXX.log)"
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

json_encode_object() {
  python -c 'import json,sys; print(json.dumps(dict(arg.split("=", 1) for arg in sys.argv[1:])))' "$@"
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

if [[ -n "${REMINDER_TITLE}" ]]; then
  reminder_body="$(json_encode_object "title=${REMINDER_TITLE}")"
  if [[ -n "${REMINDER_LIST}" ]]; then
    reminder_body="$(json_encode_object "title=${REMINDER_TITLE}" "list=${REMINDER_LIST}")"
  fi
  request POST /v1/reminders 201 "${reminder_body}" -H "X-Steersman-Token: ${TOKEN}" -H 'Idempotency-Key: gut-check-reminder-1'
fi

if [[ -n "${IMESSAGE_TO}" || -n "${IMESSAGE_TEXT}" ]]; then
  if [[ -z "${IMESSAGE_TO}" || -z "${IMESSAGE_TEXT}" ]]; then
    echo "ERROR: both STEERSMAN_GUTCHECK_IMESSAGE_TO and STEERSMAN_GUTCHECK_IMESSAGE_TEXT are required when sending a gut-check iMessage" >&2
    exit 1
  fi
  imessage_body="$(json_encode_object "to=${IMESSAGE_TO}" "text=${IMESSAGE_TEXT}")"
  request POST /v1/imessage/send 201 "${imessage_body}" -H "X-Steersman-Token: ${TOKEN}" -H 'Idempotency-Key: gut-check-imessage-1'
fi

echo "Gut check passed"
