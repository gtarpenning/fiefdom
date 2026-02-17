#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import uuid

from cupbearer.db.connection import connect_sqlite
from cupbearer.db.migrations import apply_migrations


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed local Cupbearer development data.")
    parser.add_argument(
        "--db-path",
        default="data/cupbearer.db",
        help="Path to SQLite database file.",
    )
    args = parser.parse_args()

    apply_migrations(args.db_path)
    with connect_sqlite(args.db_path) as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO contacts (id, name, channel, address)
            VALUES (?, ?, ?, ?);
            """,
            ("owner", "Owner", "local", "owner@cupbearer"),
        )

        connection.execute(
            """
            INSERT OR IGNORE INTO skills (id, name, description)
            VALUES (?, ?, ?);
            """,
            ("skill_ping", "ping", "Baseline connectivity skill"),
        )

        connection.execute(
            """
            INSERT OR IGNORE INTO skill_versions (
                id, skill_id, version, entrypoint, manifest_json, is_active
            ) VALUES (?, ?, ?, ?, ?, ?);
            """,
            (
                "skill_ping_v1",
                "skill_ping",
                "1.0.0",
                "skills.ping:run",
                json.dumps({"name": "ping", "inputs": {}, "permissions": []}),
                1,
            ),
        )

        # Seed one immutable event to verify append-only event paths in dev.
        connection.execute(
            """
            INSERT OR IGNORE INTO events (
                id, direction, source, type, payload, idempotency_key
            ) VALUES (?, ?, ?, ?, ?, ?);
            """,
            (
                "seed_event_1",
                "inbound",
                "seed",
                "system.bootstrap",
                json.dumps({"message": "Cupbearer bootstrap complete"}),
                f"seed-{uuid.uuid4()}",
            ),
        )
        connection.commit()

    print("Seed completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
