"""#53: pending photo reports get re-reviewed, and the new verdict is saved."""

import threading
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.config import MAX_PENDING_REVIEW_RETRIES
from app.main import create_app
from app.reports import PhotoVerdict
from app.storage import MemoryReportStore, StoredReport
from tests.test_report_api import A_TO_D, report, vote


class SwitchableReviewer:
    """The photo agent: down until `recover()` is called, then confirms."""

    def __init__(self) -> None:
        self.verdict = PhotoVerdict.UNAVAILABLE
        self.calls = 0

    def recover(self, verdict: PhotoVerdict = PhotoVerdict.CONFIRMED) -> None:
        self.verdict = verdict

    def __call__(self, photo: bytes) -> PhotoVerdict:
        self.calls += 1
        return self.verdict


def shortest_m(client: TestClient) -> float:
    return client.get("/route", params={**A_TO_D, "mode": "shortest"}).json()["distance_m"]


def test_pending_photo_is_confirmed_once_the_agent_is_back(street_graph):
    reviewer, store = SwitchableReviewer(), MemoryReportStore()
    with TestClient(create_app(graph=street_graph, review_photo=reviewer, store=store)) as client:
        assert report(client).json()["outcome"] == "pending"
        assert shortest_m(client) == 200.0  # pending doesn't block

        reviewer.recover()
        resolved = client.app.state.retry_pending_photos()

        assert resolved == 1
        assert shortest_m(client) == 300.0  # now blocked: detour via C
        [listed] = client.get("/reports").json()
        assert listed["verification"] == "confirmed"


def test_retry_while_the_agent_is_still_down_changes_nothing(street_graph):
    reviewer = SwitchableReviewer()
    with TestClient(create_app(graph=street_graph, review_photo=reviewer, store=MemoryReportStore())) as client:
        report(client)

        assert client.app.state.retry_pending_photos() == 0
        assert client.get("/reports").json()[0]["verification"] == "pending"


def test_rejected_on_retry_becomes_unverified(street_graph):
    reviewer = SwitchableReviewer()
    with TestClient(create_app(graph=street_graph, review_photo=reviewer, store=MemoryReportStore())) as client:
        report(client)
        reviewer.recover(PhotoVerdict.REJECTED)
        client.app.state.retry_pending_photos()

        assert client.get("/reports").json()[0]["verification"] == "unverified"
        assert shortest_m(client) == 200.0


def test_verdict_from_a_retry_survives_a_restart(street_graph):
    reviewer, store = SwitchableReviewer(), MemoryReportStore()
    with TestClient(create_app(graph=street_graph, review_photo=reviewer, store=store)) as client:
        report(client)
        reviewer.recover()
        client.app.state.retry_pending_photos()

    [row] = store.all()
    assert row.status is PhotoVerdict.CONFIRMED
    assert row.photo is None  # photos are only kept while they might be re-reviewed

    calls_before = reviewer.calls
    with TestClient(create_app(graph=street_graph, review_photo=reviewer, store=store)) as client:
        assert shortest_m(client) == 300.0
    assert reviewer.calls == calls_before  # replay never calls the agent


def test_memory_store_update_status_only_touches_that_report():
    store = MemoryReportStore()
    now = datetime(2026, 11, 22, tzinfo=UTC)
    store.add(StoredReport("r_1", "A-B", "u1", 0, 0, True, now, status=PhotoVerdict.UNAVAILABLE, photo=b"x"))
    store.add(StoredReport("r_2", "B-D", "u2", 0, 0, True, now, status=PhotoVerdict.UNAVAILABLE, photo=b"y"))

    decided = datetime(2026, 11, 22, 1, tzinfo=UTC)
    store.update_status("r_1", PhotoVerdict.CONFIRMED, decided)

    rows = {row.report_id: row for row in store.all()}
    assert (rows["r_1"].status, rows["r_1"].photo, rows["r_1"].decided_at) == (PhotoVerdict.CONFIRMED, None, decided)
    assert rows["r_2"].decided_at is None
    assert (rows["r_2"].status, rows["r_2"].photo) == (PhotoVerdict.UNAVAILABLE, b"y")


# Codex review of #63: replay order, retry cap, and stopping between photos.


def test_late_confirmation_still_blocks_after_a_restart_despite_earlier_open_votes(street_graph):
    # Live: 4 "open" votes on an open sidewalk change nothing, then the late confirmation
    # blocks it (and clears earlier votes). Replay must apply them in that same order.
    reviewer, store = SwitchableReviewer(), MemoryReportStore()
    with TestClient(create_app(graph=street_graph, review_photo=reviewer, store=store)) as client:
        report(client)
        for user in ["u1", "u2", "u3", "u4"]:
            vote(client, "A-B", user, blocked=False)
        reviewer.recover()
        client.app.state.retry_pending_photos()
        assert shortest_m(client) == 300.0

    with TestClient(create_app(graph=street_graph, review_photo=reviewer, store=store)) as client:
        assert shortest_m(client) == 300.0  # still blocked after the restart


def test_a_pending_photo_is_retried_at_most_max_times(street_graph):
    reviewer = SwitchableReviewer()  # down the whole time
    with TestClient(create_app(graph=street_graph, review_photo=reviewer, store=MemoryReportStore())) as client:
        report(client)
        calls_after_report = reviewer.calls
        for _ in range(MAX_PENDING_REVIEW_RETRIES + 3):
            client.app.state.retry_pending_photos()

    assert reviewer.calls - calls_after_report == MAX_PENDING_REVIEW_RETRIES


def test_retry_stops_before_the_next_photo_once_asked_to(street_graph):
    reviewer = SwitchableReviewer()
    with TestClient(create_app(graph=street_graph, review_photo=reviewer, store=MemoryReportStore())) as client:
        report(client)
        calls_after_report = reviewer.calls
        stop = threading.Event()
        stop.set()

        client.app.state.retry_pending_photos(stop)

    assert reviewer.calls == calls_after_report


def test_a_late_verdict_replays_after_votes_stored_at_the_same_instant(street_graph):
    # Windows clocks tick ~15 ms, so a vote and a late verdict can share a timestamp.
    reported, tie = datetime(2026, 11, 22, 1, tzinfo=UTC), datetime(2026, 11, 22, 2, tzinfo=UTC)
    store = MemoryReportStore()
    store.add(StoredReport("r_1", "A-B", "u0", 0, 0, True, reported, status=PhotoVerdict.CONFIRMED, decided_at=tie))
    for n in range(1, 5):
        store.add(StoredReport(f"v_{n}", "A-B", f"u{n}", 0, 0, False, tie))

    with TestClient(create_app(graph=street_graph, review_photo=SwitchableReviewer(), store=store)) as client:
        assert shortest_m(client) == 300.0
