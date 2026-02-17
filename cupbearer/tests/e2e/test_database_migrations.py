from __future__ import annotations

import sqlite3
import subprocess

import pytest


@pytest.mark.e2e
def test_migrations_create_required_tables_and_upgrade_idempotently(tmp_path) -> None:
    db_path = tmp_path / "cupbearer.db"

    first = subprocess.run(
        ["python", "scripts/migrate.py", "--db-path", str(db_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert first.returncode == 0
    assert "Applied migrations:" in first.stdout

    second = subprocess.run(
        ["python", "scripts/migrate.py", "--db-path", str(db_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert second.returncode == 0
    assert "No pending migrations" in second.stdout

    with sqlite3.connect(db_path) as connection:
        names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table';"
            ).fetchall()
        }

    expected = {
        "events",
        "jobs",
        "contacts",
        "threads",
        "messages",
        "skills",
        "skill_versions",
        "skill_runs",
        "auth_accounts",
        "oauth_tokens",
        "memory_references",
        "schema_migrations",
    }
    assert expected.issubset(names)


@pytest.mark.e2e
def test_events_table_is_append_only(tmp_path) -> None:
    db_path = tmp_path / "cupbearer.db"
    migrated = subprocess.run(
        ["python", "scripts/migrate.py", "--db-path", str(db_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert migrated.returncode == 0

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO events (id, direction, source, type, payload)
            VALUES ('evt_1', 'inbound', 'test', 'message.received', '{"ok":true}');
            """
        )

        with pytest.raises(sqlite3.DatabaseError, match="events are immutable"):
            connection.execute(
                "UPDATE events SET payload = '{\"ok\":false}' WHERE id = 'evt_1';"
            )

        with pytest.raises(sqlite3.DatabaseError, match="events are immutable"):
            connection.execute("DELETE FROM events WHERE id = 'evt_1';")
