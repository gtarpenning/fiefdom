#!/usr/bin/env python
from __future__ import annotations

import argparse

from cupbearer.db.migrations import apply_migrations


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply Cupbearer SQLite migrations.")
    parser.add_argument(
        "--db-path",
        default="data/cupbearer.db",
        help="Path to SQLite database file.",
    )
    args = parser.parse_args()

    applied = apply_migrations(args.db_path)
    if applied:
        print(f"Applied migrations: {', '.join(applied)}")
    else:
        print("No pending migrations")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
