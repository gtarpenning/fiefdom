from __future__ import annotations

import sqlite3
from pathlib import Path

from cupbearer.db.connection import connect_sqlite

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"


def _migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def _ensure_migration_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    connection.commit()


def _applied_versions(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("SELECT version FROM schema_migrations;").fetchall()
    return {row["version"] for row in rows}


def apply_migrations(db_path: str) -> list[str]:
    applied_now: list[str] = []

    with connect_sqlite(db_path) as connection:
        _ensure_migration_table(connection)
        existing = _applied_versions(connection)

        for file in _migration_files():
            version = file.stem
            if version in existing:
                continue

            script = file.read_text(encoding="utf-8")
            with connection:
                connection.executescript(script)
                connection.execute(
                    "INSERT INTO schema_migrations(version) VALUES (?);",
                    (version,),
                )
            applied_now.append(version)

    return applied_now
