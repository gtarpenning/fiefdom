import os
import plistlib
import shutil
import subprocess
import sys
import tempfile

import pytest

from tests.e2e.utils import free_port
from tests.e2e.utils import request_json
from tests.e2e.utils import run_server
from tests.e2e.utils import wait_for_http
from tests.e2e.utils import wait_for_jsonl


def test_infra_endpoints_and_startup_guards_e2e() -> None:
    with run_server() as base_url:
        status, health_payload = request_json(f"{base_url}/healthz")
        assert status == 200
        assert health_payload == {"status": "ok"}

        status, root_payload = request_json(f"{base_url}/")
        assert status == 200
        assert root_payload["service"] == "steersman"
        assert root_payload["health"] == "/healthz"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "steersman",
            "serve",
            "--host",
            "0.0.0.0",
            "--port",
            "8765",
        ],
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}"
    assert "Refusing non-loopback bind host" in combined


def test_v1_auth_policy_and_validation_flow_e2e() -> None:
    env = {"STEERSMAN_AUTH_TOKEN": "test-token"}
    with run_server(env=env) as base_url:
        status, payload = request_json(f"{base_url}/v1/ping")
        assert status == 401
        assert payload["error"]["kind"] == "auth_denied"
        assert payload["error"]["retryable"] is False
        assert payload["request_id"]
        assert payload["audit_ref"]

        status, payload = request_json(
            f"{base_url}/v1/ping",
            headers={"X-Steersman-Token": "test-token"},
        )
        assert status == 200
        assert payload["result"] == {"pong": "ok"}

        status, payload = request_json(
            f"{base_url}/v1/echo",
            headers={"X-Steersman-Token": "test-token"},
        )
        assert status == 422
        assert payload["error"]["kind"] == "invalid_input"
        assert payload["error"]["retryable"] is False


def test_v1_success_audit_and_mutation_idempotency_flow_e2e() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        audit_path = os.path.join(temp_dir, "audit.jsonl")
        env = {
            "STEERSMAN_AUTH_TOKEN": "test-token",
            "STEERSMAN_AUDIT_LOG_PATH": audit_path,
        }

        with run_server(env=env) as base_url:
            headers = {"X-Steersman-Token": "test-token"}

            status, ping_payload = request_json(f"{base_url}/v1/ping", headers=headers)
            assert status == 200
            assert ping_payload["result"] == {"pong": "ok"}

            events = wait_for_jsonl(audit_path)
            assert events
            assert any(
                event["audit_ref"] == ping_payload["audit_ref"]
                and event["action"] == "v1.ping"
                for event in events
            )

            status, missing_key_payload = request_json(
                f"{base_url}/v1/notes",
                method="POST",
                headers=headers,
                body={"text": "buy milk"},
            )
            assert status == 400
            assert missing_key_payload["error"]["kind"] == "invalid_input"

            idem_headers = {**headers, "Idempotency-Key": "abc-123"}
            status_1, created_1 = request_json(
                f"{base_url}/v1/notes",
                method="POST",
                headers=idem_headers,
                body={"text": "buy milk"},
            )
            assert status_1 == 201

            status_2, created_2 = request_json(
                f"{base_url}/v1/notes",
                method="POST",
                headers=idem_headers,
                body={"text": "buy milk"},
            )
            assert status_2 == 201
            assert created_2 == created_1


def test_v1_skill_catalog_and_manifest_mapped_capabilities_flow_e2e() -> None:
    env = {"STEERSMAN_AUTH_TOKEN": "test-token"}
    with run_server(env=env) as base_url:
        headers = {"X-Steersman-Token": "test-token"}

        status, skills_payload = request_json(f"{base_url}/v1/skills", headers=headers)
        assert status == 200
        skills = skills_payload["result"]["skills"]
        assert any(skill["name"] == "system" for skill in skills)
        assert any(skill["name"] == "notes" for skill in skills)
        assert any(skill["name"] == "reminders" for skill in skills)
        assert any(skill["name"] == "imessage" for skill in skills)

        status, health_payload = request_json(
            f"{base_url}/v1/skills/system/health",
            headers=headers,
        )
        assert status == 200
        assert health_payload["result"]["status"] == "ok"

        status, req_payload = request_json(
            f"{base_url}/v1/skills/notes/requirements",
            headers=headers,
        )
        assert status == 200
        assert "operation_capabilities" in req_payload["result"]
        assert req_payload["result"]["operation_capabilities"]["create"] == "notes.write"

        status, reminders_req_payload = request_json(
            f"{base_url}/v1/skills/reminders/requirements",
            headers=headers,
        )
        assert status == 200
        assert reminders_req_payload["result"]["operation_capabilities"]["list"] == (
            "reminders.read"
        )
        assert reminders_req_payload["result"]["operation_capabilities"]["create"] == (
            "reminders.write"
        )

        status, reminders_payload = request_json(
            f"{base_url}/v1/reminders",
            headers=headers,
        )
        assert status == 200
        assert isinstance(reminders_payload["result"]["items"], list)

        status, notes_payload = request_json(
            f"{base_url}/v1/notes",
            method="POST",
            headers={**headers, "Idempotency-Key": "catalog-flow-create"},
            body={"text": "will pass"},
        )
        assert status == 201
        assert notes_payload["result"]["text"] == "will pass"

        status, imessage_req_payload = request_json(
            f"{base_url}/v1/skills/imessage/requirements",
            headers=headers,
        )
        assert status == 200
        assert imessage_req_payload["result"]["operation_capabilities"]["list_chats"] == (
            "imessage.read"
        )
        assert imessage_req_payload["result"]["operation_capabilities"]["send"] == (
            "imessage.send"
        )


def test_gut_check_script_optional_skill_actions_e2e() -> None:
    port = free_port()
    fake_bin = os.path.join(os.path.dirname(__file__), "fake_bin")
    with tempfile.TemporaryDirectory() as temp_dir:
        env = {
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}",
            "FAKE_STEERSMAN_STATE_DIR": temp_dir,
            "STEERSMAN_AUTH_TOKEN": "test-token",
            "STEERSMAN_HOST": "127.0.0.1",
            "STEERSMAN_PORT": str(port),
            "STEERSMAN_GUTCHECK_IMESSAGE_TO": "+14155550100",
        }
        result = subprocess.run(
            ["bash", "scripts/gut_check.sh"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )

    assert result.returncode == 0
    assert "[POST /v1/reminders] status=201 expected=201" in result.stdout
    assert "[POST /v1/imessage/send] status=201 expected=201" in result.stdout


def test_gut_check_script_fails_without_required_skill_binaries_e2e() -> None:
    port = free_port()
    with tempfile.TemporaryDirectory() as temp_dir:
        python_path = os.path.join(temp_dir, "python")
        with open(python_path, "w", encoding="utf-8") as handle:
            handle.write(f"#!/usr/bin/env bash\nexec {sys.executable} \"$@\"\n")
        os.chmod(python_path, 0o755)

        env = {
            **os.environ,
            "PATH": f"{temp_dir}:/usr/bin:/bin",
            "STEERSMAN_AUTH_TOKEN": "test-token",
            "STEERSMAN_HOST": "127.0.0.1",
            "STEERSMAN_PORT": str(port),
        }
        result = subprocess.run(
            ["bash", "scripts/gut_check.sh"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )

    assert result.returncode != 0
    assert "[GET /v1/reminders] status=503 expected=200" in result.stdout


def test_gut_check_script_remote_target_e2e() -> None:
    env = {"STEERSMAN_AUTH_TOKEN": "test-token"}
    with run_server(env=env) as base_url:
        result = subprocess.run(
            [
                "bash",
                "scripts/gut_check.sh",
                "--target",
                "remote",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            env={
                **os.environ,
                "STEERSMAN_AUTH_TOKEN": "test-token",
                "STEERSMAN_GUTCHECK_BASE_URL": base_url,
            },
        )

    assert result.returncode == 0
    assert f"Running Steersman gut check against {base_url}" in result.stdout


def test_gut_check_script_local_target_with_fake_bins_e2e() -> None:
    port = free_port()
    fake_bin = os.path.join(os.path.dirname(__file__), "fake_bin")
    with tempfile.TemporaryDirectory() as temp_dir:
        python_path = os.path.join(temp_dir, "python")
        with open(python_path, "w", encoding="utf-8") as handle:
            handle.write(f"#!/usr/bin/env bash\nexec {sys.executable} \"$@\"\n")
        os.chmod(python_path, 0o755)

        env = {
            **os.environ,
            "PATH": f"{fake_bin}:{temp_dir}:/usr/bin:/bin",
            "STEERSMAN_AUTH_TOKEN": "test-token",
            "STEERSMAN_HOST": "127.0.0.1",
            "STEERSMAN_PORT": str(port),
        }
        result = subprocess.run(
            ["bash", "scripts/gut_check.sh", "--target", "local"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )

    assert result.returncode == 0
    assert "[GET /v1/reminders] status=200 expected=200" in result.stdout


def test_cli_start_status_and_doctor_flow_e2e() -> None:
    port = free_port()
    env = {"STEERSMAN_AUTH_TOKEN": "test-token"}
    start_proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "steersman",
            "start",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, **env},
    )
    base_url = f"http://127.0.0.1:{port}"

    try:
        payload = wait_for_http(f"{base_url}/healthz")
        assert payload == {"status": "ok"}

        status_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "steersman",
                "status",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert status_result.returncode == 0
        assert "ok" in status_result.stdout.lower()
    finally:
        start_proc.terminate()
        start_proc.wait(timeout=5)

    doctor_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "steersman",
            "doctor",
            "--host",
            "0.0.0.0",
        ],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert doctor_result.returncode != 0
    assert "loopback" in f"{doctor_result.stdout}\n{doctor_result.stderr}".lower()


def test_cli_launchd_install_writes_plist_e2e() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        plist_path = os.path.join(temp_dir, "local.steersman.test.plist")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "steersman",
                "start",
                "--launchd",
                "--launchd-no-load",
                "--launchd-label",
                "local.steersman.test",
                "--launchd-plist-path",
                plist_path,
                "--host",
                "127.0.0.1",
                "--port",
                "8875",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert os.path.exists(plist_path)
        with open(plist_path, "rb") as handle:
            payload = plistlib.load(handle)
        assert payload["Label"] == "local.steersman.test"
        args = payload["ProgramArguments"]
        assert "-m" in args
        assert "steersman" in args
        assert "serve" in args
        assert "8875" in args


def test_cli_launchd_status_reports_installed_not_loaded_e2e() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        plist_path = os.path.join(temp_dir, "local.steersman.status.plist")
        install = subprocess.run(
            [
                sys.executable,
                "-m",
                "steersman",
                "start",
                "--launchd",
                "--launchd-no-load",
                "--launchd-label",
                "local.steersman.status",
                "--launchd-plist-path",
                plist_path,
                "--host",
                "127.0.0.1",
                "--port",
                "8876",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert install.returncode == 0

        status = subprocess.run(
            [
                sys.executable,
                "-m",
                "steersman",
                "status",
                "--launchd",
                "--launchd-label",
                "local.steersman.status",
                "--launchd-plist-path",
                plist_path,
                "--host",
                "127.0.0.1",
                "--port",
                "8876",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert status.returncode != 0
        stdout = status.stdout.lower()
        assert "launchd installed: yes" in stdout
        assert "launchd loaded: no" in stdout


def test_cli_launchd_stop_unloads_agent_e2e() -> None:
    port = free_port()
    label = f"local.steersman.stop.{os.getpid()}"
    with tempfile.TemporaryDirectory() as temp_dir:
        plist_path = os.path.join(temp_dir, f"{label}.plist")
        install = subprocess.run(
            [
                sys.executable,
                "-m",
                "steersman",
                "start",
                "--launchd",
                "--launchd-label",
                label,
                "--launchd-plist-path",
                plist_path,
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert install.returncode == 0
        wait_for_http(f"http://127.0.0.1:{port}/healthz", timeout_s=10.0)

        stop = subprocess.run(
            [
                sys.executable,
                "-m",
                "steersman",
                "stop",
                "--launchd",
                "--launchd-label",
                label,
                "--launchd-plist-path",
                plist_path,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert stop.returncode == 0

        status = subprocess.run(
            [
                sys.executable,
                "-m",
                "steersman",
                "status",
                "--launchd",
                "--launchd-label",
                label,
                "--launchd-plist-path",
                plist_path,
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert status.returncode != 0
        assert "launchd loaded: no" in status.stdout.lower()


@pytest.mark.skipif(
    os.environ.get("STEERSMAN_E2E_LAUNCHD") != "1",
    reason="Set STEERSMAN_E2E_LAUNCHD=1 for native launchd bootstrap E2E.",
)
def test_cli_launchd_native_bootstrap_status_flow_e2e() -> None:
    port = free_port()
    label = f"local.steersman.e2e.{os.getpid()}"
    with tempfile.TemporaryDirectory() as temp_dir:
        plist_path = os.path.join(temp_dir, f"{label}.plist")
        uid = os.getuid()
        install = subprocess.run(
            [
                sys.executable,
                "-m",
                "steersman",
                "start",
                "--launchd",
                "--launchd-label",
                label,
                "--launchd-plist-path",
                plist_path,
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert install.returncode == 0
        try:
            payload = wait_for_http(f"http://127.0.0.1:{port}/healthz", timeout_s=10.0)
            assert payload == {"status": "ok"}

            status = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "steersman",
                    "status",
                    "--launchd",
                    "--launchd-label",
                    label,
                    "--launchd-plist-path",
                    plist_path,
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert status.returncode == 0
            stdout = status.stdout.lower()
            assert "launchd loaded: yes" in stdout
            assert "health: ok" in stdout
        finally:
            subprocess.run(
                ["launchctl", "bootout", f"gui/{uid}/{label}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
def test_v1_reminders_read_create_flow_e2e() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        audit_path = os.path.join(temp_dir, "audit.jsonl")
        env = {
            "STEERSMAN_AUTH_TOKEN": "test-token",
            "STEERSMAN_AUDIT_LOG_PATH": audit_path,
        }
        headers = {"X-Steersman-Token": "test-token"}

        with run_server(env=env) as base_url:
            status, initial = request_json(f"{base_url}/v1/reminders", headers=headers)
            assert status == 200
            assert isinstance(initial["result"]["items"], list)

            status, missing_idem = request_json(
                f"{base_url}/v1/reminders",
                method="POST",
                headers=headers,
                body={"title": "Call mom", "list": "Personal", "due": "tomorrow"},
            )
            assert status == 400
            assert missing_idem["error"]["kind"] == "invalid_input"

            create_headers = {**headers, "Idempotency-Key": "reminders-create-1"}
            status_1, created_1 = request_json(
                f"{base_url}/v1/reminders",
                method="POST",
                headers=create_headers,
                body={
                    "title": "Call mom",
                    "list": "Personal",
                    "due": "tomorrow",
                    "notes": "Discuss weekend plans",
                },
            )
            assert status_1 == 201
            item_1 = created_1["result"]["item"]
            assert item_1["title"] == "Call mom"
            assert item_1["list"] == "Personal"
            assert item_1["due"] == "tomorrow"
            assert item_1["status"] == "open"

            status_2, created_2 = request_json(
                f"{base_url}/v1/reminders",
                method="POST",
                headers=create_headers,
                body={
                    "title": "Call mom",
                    "list": "Personal",
                    "due": "tomorrow",
                    "notes": "Different payload should replay",
                },
            )
            assert status_2 == 201
            assert created_2 == created_1

            status, filtered = request_json(
                f"{base_url}/v1/reminders?list=Personal",
                headers=headers,
            )
            assert status == 200
            assert any(item["id"] == item_1["id"] for item in filtered["result"]["items"])

        events = wait_for_jsonl(audit_path)
        assert any(event["action"] == "v1.reminders.create" for event in events)


@pytest.mark.skipif(shutil.which("remindctl") is None, reason="remindctl not found on PATH")
def test_v1_reminders_remindctl_backend_flow_e2e() -> None:
    env = {
        "STEERSMAN_AUTH_TOKEN": "test-token",
    }
    headers = {"X-Steersman-Token": "test-token", "Idempotency-Key": "remindctl-reminders-e2e-1"}

    with run_server(env=env, use_fake_bins=False) as base_url:
        title = "steersman native e2e"
        status, created = request_json(
            f"{base_url}/v1/reminders",
            method="POST",
            headers=headers,
            body={
                "title": title,
                "notes": "created by steersman native e2e",
                "list": "steersman",
                "priority": 5,
            },
            timeout_s=20.0,
        )
        assert status == 201
        item = created["result"]["item"]
        assert item["title"] == title
        assert item["list"] == "steersman"

        status, listed = request_json(
            f"{base_url}/v1/reminders?list=steersman&status=open",
            headers={"X-Steersman-Token": "test-token"},
            timeout_s=20.0,
        )
        assert status == 200
        assert any(reminder["id"] == item["id"] for reminder in listed["result"]["items"])


def test_v1_reminders_remindctl_missing_binary_returns_dependency_error_e2e() -> None:
    env = {
        "STEERSMAN_AUTH_TOKEN": "test-token",
        "PATH": "",
    }
    with run_server(env=env, use_fake_bins=False) as base_url:
        status, payload = request_json(
            f"{base_url}/v1/reminders",
            headers={"X-Steersman-Token": "test-token"},
            timeout_s=20.0,
        )
        assert status == 503
        assert payload["error"]["kind"] == "dependency_unavailable"
        assert "remindctl binary not found" in payload["error"]["message"]


def test_v1_reminders_remindctl_flagged_rejected_e2e() -> None:
    env = {
        "STEERSMAN_AUTH_TOKEN": "test-token",
        "PATH": "",
    }
    with run_server(env=env, use_fake_bins=False) as base_url:
        status, payload = request_json(
            f"{base_url}/v1/reminders",
            method="POST",
            headers={
                "X-Steersman-Token": "test-token",
                "Idempotency-Key": "flagged-rejected",
            },
            body={
                "title": "test flagged not yet supported",
                "list": "steersman",
                "flagged": True,
            },
            timeout_s=20.0,
        )
        assert status == 400
        assert payload["error"]["kind"] == "invalid_input"
        assert "flagged is not supported" in payload["error"]["message"]


def test_v1_reminders_remindctl_does_not_recreate_existing_list_e2e() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        log_path = os.path.join(temp_dir, "fake-remindctl.log")
        cmd_path = os.path.join(temp_dir, "remindctl")
        with open(cmd_path, "w", encoding="utf-8") as handle:
            handle.write(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "echo \"$*\" >> \"$FAKE_REMINDCTL_LOG\"\n"
                "if [[ \"$1\" == \"list\" && \"$2\" == \"--json\" ]]; then\n"
                "  echo '[{\"id\":\"list-1\",\"title\":\"steersman\",\"reminderCount\":0,\"overdueCount\":0}]'\n"
                "  exit 0\n"
                "fi\n"
                "if [[ \"$1\" == \"add\" ]]; then\n"
                "  echo '{\"id\":\"rem-1\",\"isCompleted\":false,\"listID\":\"list-1\",\"listName\":\"steersman\",\"priority\":\"medium\",\"title\":\"test title\",\"notes\":null,\"dueDate\":null}'\n"
                "  exit 0\n"
                "fi\n"
                "if [[ \"$1\" == \"list\" && \"$2\" == \"steersman\" && \"$3\" == \"--create\" ]]; then\n"
                "  echo 'unexpected create call' 1>&2\n"
                "  exit 55\n"
                "fi\n"
                "echo 'unexpected call' 1>&2\n"
                "exit 56\n"
            )
        os.chmod(cmd_path, 0o755)

        env = {
            "STEERSMAN_AUTH_TOKEN": "test-token",
            "PATH": f"{temp_dir}:{os.environ.get('PATH', '')}",
            "FAKE_REMINDCTL_LOG": log_path,
        }
        with run_server(env=env, use_fake_bins=False) as base_url:
            status, payload = request_json(
                f"{base_url}/v1/reminders",
                method="POST",
                headers={
                    "X-Steersman-Token": "test-token",
                    "Idempotency-Key": "no-recreate-list",
                },
                body={
                    "title": "test title",
                    "list": "steersman",
                    "priority": 5,
                },
            )
            assert status == 201
            assert payload["result"]["item"]["id"] == "rem-1"

        with open(log_path, "r", encoding="utf-8") as handle:
            calls = [line.strip() for line in handle if line.strip()]
        assert any(call == "list --json" for call in calls)
        assert any(call.startswith("add ") for call in calls)
        assert not any(call.startswith("list steersman --create") for call in calls)


def test_v1_imessage_read_send_flow_e2e() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        audit_path = os.path.join(temp_dir, "audit.jsonl")
        env = {
            "STEERSMAN_AUTH_TOKEN": "test-token",
            "STEERSMAN_AUDIT_LOG_PATH": audit_path,
        }
        headers = {"X-Steersman-Token": "test-token"}

        with run_server(env=env) as base_url:
            status, chats = request_json(f"{base_url}/v1/imessage/chats", headers=headers)
            assert status == 200
            assert isinstance(chats["result"]["items"], list)

            status, missing = request_json(
                f"{base_url}/v1/imessage/send",
                method="POST",
                headers=headers,
                body={"to": "+14155550100", "text": "hello"},
            )
            assert status == 400
            assert missing["error"]["kind"] == "invalid_input"

            send_headers = {**headers, "Idempotency-Key": "imessage-send-1"}
            status_1, sent_1 = request_json(
                f"{base_url}/v1/imessage/send",
                method="POST",
                headers=send_headers,
                body={"to": "+14155550100", "text": "hello from steersman"},
            )
            assert status_1 == 201
            assert sent_1["result"]["status"] == "sent"

            status_2, sent_2 = request_json(
                f"{base_url}/v1/imessage/send",
                method="POST",
                headers=send_headers,
                body={"to": "+14155550100", "text": "different payload should replay"},
            )
            assert status_2 == 201
            assert sent_2 == sent_1

        events = wait_for_jsonl(audit_path)
        assert any(event["action"] == "v1.imessage.send" for event in events)


def test_v1_imessage_missing_binary_returns_dependency_error_e2e() -> None:
    env = {
        "STEERSMAN_AUTH_TOKEN": "test-token",
        "PATH": "",
    }
    with run_server(env=env, use_fake_bins=False) as base_url:
        status, payload = request_json(
            f"{base_url}/v1/imessage/chats",
            headers={"X-Steersman-Token": "test-token"},
            timeout_s=20.0,
        )
        assert status == 503
        assert payload["error"]["kind"] == "dependency_unavailable"
        assert "imsg binary not found" in payload["error"]["message"]


@pytest.mark.skipif(shutil.which("imsg") is None, reason="imsg not found on PATH")
def test_v1_imessage_imsg_backend_chats_flow_e2e() -> None:
    env = {
        "STEERSMAN_AUTH_TOKEN": "test-token",
    }
    with run_server(env=env, use_fake_bins=False) as base_url:
        status, payload = request_json(
            f"{base_url}/v1/imessage/chats?limit=3",
            headers={"X-Steersman-Token": "test-token"},
            timeout_s=20.0,
        )
        assert status == 200
        assert isinstance(payload["result"]["items"], list)
