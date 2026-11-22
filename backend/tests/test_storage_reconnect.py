"""#61: a dropped Postgres connection is retried once inside add()."""

from datetime import UTC, datetime

import psycopg

from app import storage
from app.storage import PostgresReportStore, StoredReport


class FakeConnection:
    def __init__(self, fail_inserts: int) -> None:
        self.fail_inserts = fail_inserts
        self.inserts = 0
        self.closed = False
        self.broken = False

    def execute(self, sql, params=None):
        if sql.lstrip().upper().startswith("INSERT"):
            if self.fail_inserts:
                self.fail_inserts -= 1
                raise psycopg.OperationalError("server closed the connection unexpectedly")
            self.inserts += 1
        return self


ROW = StoredReport("v_1", "A-B", "u1", 42.35, -71.1, True, datetime(2026, 11, 22, tzinfo=UTC))


def test_insert_on_a_dropped_connection_reconnects_once_and_succeeds(monkeypatch):
    connections = [FakeConnection(fail_inserts=1), FakeConnection(fail_inserts=0)]
    monkeypatch.setattr(storage.psycopg, "connect", lambda *args, **kwargs: connections.pop(0))
    store = PostgresReportStore("fake")

    store.add(ROW)

    assert connections == []  # it reconnected exactly once
    assert store._conn.inserts == 1


def test_a_second_failure_is_raised(monkeypatch):
    connections = [FakeConnection(fail_inserts=1), FakeConnection(fail_inserts=1)]
    monkeypatch.setattr(storage.psycopg, "connect", lambda *args, **kwargs: connections.pop(0))
    store = PostgresReportStore("fake")

    try:
        store.add(ROW)
    except psycopg.OperationalError:
        return
    raise AssertionError("expected the second failure to be raised")
