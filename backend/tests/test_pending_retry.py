"""#53: pending photo reports get re-reviewed, and the new verdict is saved."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.main import create_app
from app.reports import PhotoVerdict
from app.storage import MemoryReportStore, StoredReport
from tests.test_report_api import A_TO_D, report


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

    store.update_status("r_1", PhotoVerdict.CONFIRMED)

    rows = {row.report_id: row for row in store.all()}
    assert (rows["r_1"].status, rows["r_1"].photo) == (PhotoVerdict.CONFIRMED, None)
    assert (rows["r_2"].status, rows["r_2"].photo) == (PhotoVerdict.UNAVAILABLE, b"y")
