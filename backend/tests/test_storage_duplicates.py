"""#91: retrying an insert after a lost acknowledgement must not store the report twice."""

from datetime import UTC, datetime

import psycopg

from app import storage
from app.storage import MemoryReportStore, PostgresReportStore, StoredReport

ROW = StoredReport("r_1", "A-B", "u1", 42.35, -71.1, True, datetime(2026, 11, 22, tzinfo=UTC))


class FakeDatabase:
    """One `reports` table shared by every connection, honoring ON CONFLICT DO NOTHING."""

    def __init__(self, fail_unique_index: bool = False) -> None:
        self.rows: list[tuple] = []
        self.fail_unique_index = fail_unique_index
        self.has_unique_index = False


class FakeConnection:
    def __init__(self, db: FakeDatabase, lose_ack_on_first_insert: bool = False) -> None:
        self.db = db
        self.lose_ack = lose_ack_on_first_insert
        self.closed = False
        self.broken = False

    def execute(self, sql, params=None):
        statement = " ".join(sql.split()).upper()
        if statement.startswith("CREATE UNIQUE INDEX"):
            if self.db.fail_unique_index:
                raise psycopg.errors.UniqueViolation("could not create unique index: duplicate key")
            self.db.has_unique_index = True
        elif statement.startswith("INSERT"):
            key = (params[0], params[-1])  # report_id, reported_at
            duplicate = any((row[0], row[-1]) == key for row in self.db.rows)
            if not (duplicate and "ON CONFLICT" in statement and self.db.has_unique_index):
                self.db.rows.append(params)
            if self.lose_ack:
                self.lose_ack = False
                self.broken = True
                raise psycopg.OperationalError("server closed the connection unexpectedly")
        return self

    def close(self) -> None:
        self.closed = True


def connect_to(db: FakeDatabase, first: FakeConnection):
    connections = [first]

    def connect(*args, **kwargs):
        return connections.pop(0) if connections else FakeConnection(db)

    return connect


def test_retry_after_a_lost_acknowledgement_stores_the_report_once(monkeypatch):
    db = FakeDatabase()
    first = FakeConnection(db, lose_ack_on_first_insert=True)
    monkeypatch.setattr(storage.psycopg, "connect", connect_to(db, first))
    store = PostgresReportStore("fake")

    store.add(ROW)

    assert len(db.rows) == 1


def test_the_dropped_connection_is_closed_before_reconnecting(monkeypatch):
    db = FakeDatabase()
    first = FakeConnection(db, lose_ack_on_first_insert=True)
    monkeypatch.setattr(storage.psycopg, "connect", connect_to(db, first))
    store = PostgresReportStore("fake")

    store.add(ROW)

    assert first.closed
    assert store._conn is not first


def test_startup_survives_existing_duplicates_blocking_the_unique_index(monkeypatch):
    db = FakeDatabase(fail_unique_index=True)
    monkeypatch.setattr(storage.psycopg, "connect", connect_to(db, FakeConnection(db)))

    store = PostgresReportStore("fake")  # must not raise
    store.add(ROW)

    assert len(db.rows) == 1


def test_memory_store_ignores_the_same_report_twice():
    store = MemoryReportStore()

    store.add(ROW)
    store.add(ROW)

    assert store.all() == [ROW]
