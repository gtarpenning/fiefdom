from __future__ import annotations

from cupbearer.db.connection import connect_sqlite
from cupbearer.db.migrations import apply_migrations


def init_database(db_path: str) -> list[str]:
    applied = apply_migrations(db_path)
    with connect_sqlite(db_path):
        # Connection context ensures database and pragmas are valid at boot.
        pass
    return applied
