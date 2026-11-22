"""Report storage: the stores themselves, and replay into SegmentReports.

The Postgres tests run only when LUMI_TEST_DATABASE_URL points at a throwaway
database with TimescaleDB. They drop and recreate the `reports` table.
"""

import os
from datetime import UTC, datetime, timedelta

import pytest

from app.reports import PhotoVerdict, SegmentReports, SegmentStatus
from app.routing import segment_key
from app.segments import SegmentIndex
from app.storage import MemoryReportStore, StoredReport, replay

T0 = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
PHOTO = b"\xff\xd8\xff\xe0fake-jpeg"
AB = segment_key("A", "B")
TEST_DATABASE_URL = os.environ.get("LUMI_TEST_DATABASE_URL")


def photo_row(report_id="r_1", status=PhotoVerdict.CONFIRMED, at=T0, segment_id="A-B"):
    return StoredReport(report_id, segment_id, "alice", 42.35, -71.1074, True, at, status=status, photo=PHOTO)


def vote_row(report_id, user_id, blocked, at=T0, segment_id="A-B"):
    return StoredReport(report_id, segment_id, user_id, 42.35, -71.1074, blocked, at)


def never_review(photo):
    raise AssertionError("replay must not call the photo reviewer")


# --- Stores (in memory always; Postgres when a test database is configured) ---------------


@pytest.fixture(params=["memory", "postgres"])
def store(request):
    if request.param == "memory":
        yield MemoryReportStore()
        return
    if not TEST_DATABASE_URL:
        pytest.skip("set LUMI_TEST_DATABASE_URL to run the Postgres store tests")
    import psycopg

    from app.storage import PostgresReportStore

    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
        conn.execute("DROP TABLE IF EXISTS reports")
    pg = PostgresReportStore(TEST_DATABASE_URL)  # creates the table again
    yield pg
    pg.close()


def test_store_returns_rows_oldest_first(store):
    store.add(vote_row("v_2", "bob", blocked=False, at=T0 + timedelta(minutes=5)))
    store.add(photo_row("r_1", at=T0))

    assert [row.report_id for row in store.all()] == ["r_1", "v_2"]


def test_rows_with_the_same_time_are_ordered_by_id(store):
    store.add(vote_row("v_1", "bob", blocked=True))
    store.add(photo_row("r_1"))

    assert [row.report_id for row in store.all()] == ["r_1", "v_1"]


def test_store_round_trips_photo_reports_and_votes(store):
    pending = photo_row("r_1", status=PhotoVerdict.UNAVAILABLE)
    ballot = vote_row("v_1", "bob", blocked=False)
    store.add(pending)
    store.add(ballot)

    assert store.all() == [pending, ballot]
    assert store.all()[0].photo == PHOTO  # pending photos come back with their bytes, for a retry


def test_photo_status_is_stored(store):
    for i, status in enumerate(PhotoVerdict):
        store.add(photo_row(f"r_{i}", status=status))

    assert [row.status for row in store.all()] == list(PhotoVerdict)


# --- Replay ------------------------------------------------------------------------


def test_replay_restores_a_confirmed_block_without_calling_the_reviewer(street_graph):
    book = SegmentReports(review_photo=never_review)

    replay([photo_row("r_1", status=PhotoVerdict.CONFIRMED)], book, SegmentIndex(street_graph))

    assert book.status(AB) is SegmentStatus.BLOCKED
    [report] = book.photo_reports()
    assert (report.report_id, report.user_id, report.verdict) == ("r_1", "alice", PhotoVerdict.CONFIRMED)


def test_replay_applies_votes_in_order(street_graph):
    rows = [photo_row("r_1")] + [
        vote_row(f"v_{i}", user, blocked=False, at=T0 + timedelta(minutes=i + 1))
        for i, user in enumerate(["u1", "u2", "u3", "u4"])
    ]
    book = SegmentReports(review_photo=never_review)

    replay(rows, book, SegmentIndex(street_graph))

    assert book.status(AB) is SegmentStatus.OPEN


def test_replay_keeps_pending_photos_pending_with_their_bytes(street_graph):
    book = SegmentReports(review_photo=never_review)

    replay([photo_row("r_1", status=PhotoVerdict.UNAVAILABLE)], book, SegmentIndex(street_graph))

    assert book.status(AB) is SegmentStatus.OPEN
    [pending] = book.photo_reports()
    assert (pending.verdict, pending.photo) == (PhotoVerdict.UNAVAILABLE, PHOTO)  # ready for a retry


def test_replay_skips_segments_missing_from_the_graph(street_graph, caplog):
    book = SegmentReports(review_photo=never_review)

    applied = replay([photo_row("r_1", segment_id="X-Y"), photo_row("r_2")], book, SegmentIndex(street_graph))

    assert applied == 1
    assert [r.report_id for r in book.photo_reports()] == ["r_2"]
    assert "X-Y" in caplog.text
