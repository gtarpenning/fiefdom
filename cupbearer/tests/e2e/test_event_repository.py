from __future__ import annotations

from cupbearer.db.connection import connect_sqlite
from cupbearer.db.migrations import apply_migrations
from cupbearer.db.repositories import SQLiteEventRepository
from cupbearer.domain.models import Event
import pytest


@pytest.mark.e2e
def test_event_repository_append_and_get(tmp_path) -> None:
    db_path = tmp_path / "cupbearer.db"
    apply_migrations(str(db_path))

    with connect_sqlite(str(db_path)) as connection:
        repo = SQLiteEventRepository(connection)
        event = Event(
            id="evt_repo_1",
            direction="inbound",
            source="test",
            type="message.received",
            payload='{"message":"hello"}',
            idempotency_key="idem-evt-repo-1",
        )
        repo.append(event)

        fetched = repo.get(event.id)

    assert fetched == event
