"""The API writes every report to the store first, and rebuilds from it on startup."""

import logging

import pytest
from fastapi.testclient import TestClient

from app import storage
from app.main import create_app
from app.reports import PhotoVerdict
from app.storage import MemoryReportStore
from tests.test_report_api import A_TO_D, JPEG, NEAR, report, reviewer, vote


def never_review(photo):
    raise AssertionError("the reviewer must not be called on startup")


def start(street_graph, store, review_photo=never_review) -> TestClient:
    return TestClient(create_app(graph=street_graph, review_photo=review_photo, store=store))


def shortest_distance(client) -> float:
    return client.get("/route", params={**A_TO_D, "mode": "shortest"}).json()["distance_m"]


def test_restart_keeps_a_blocked_segment_blocked(street_graph):
    store = MemoryReportStore()
    with start(street_graph, store, reviewer(PhotoVerdict.CONFIRMED)) as client:
        assert report(client).json()["outcome"] == "status_changed"

    with start(street_graph, store) as restarted:
        assert shortest_distance(restarted) == pytest.approx(300.0)
        [item] = restarted.get("/reports").json()
        assert item["verification"] == "confirmed"
        assert restarted.get("/segments/nearby", params=dict(zip(["lat", "lon"], NEAR["A-B"]))).json()[0][
            "status"
        ] == "blocked"


def test_votes_before_a_restart_still_count(street_graph):
    store = MemoryReportStore()
    with start(street_graph, store, reviewer(PhotoVerdict.CONFIRMED)) as client:
        report(client, user="reporter")
        for user in ["u1", "u2", "u3"]:
            vote(client, "A-B", user, blocked=False)

    with start(street_graph, store) as restarted:
        response = vote(restarted, "A-B", "u4", blocked=False)

    assert response.json() == {"outcome": "status_changed", "segment_status": "open"}


def test_abuse_limit_survives_a_restart(street_graph):
    store = MemoryReportStore()
    with start(street_graph, store) as client:
        for segment in ["A-B", "B-D", "A-C"]:
            vote(client, segment, "spammer", blocked=True)

    with start(street_graph, store) as restarted:
        response = vote(restarted, "C-D", "spammer", blocked=True)

    assert response.json()["outcome"] == "photo_required"


def test_pending_photo_stays_pending_after_restart_even_with_a_reviewer(street_graph):
    store = MemoryReportStore()
    with start(street_graph, store, review_photo=reviewer(PhotoVerdict.UNAVAILABLE)) as client:
        report_id = report(client).json()["report_id"]

    # The new reviewer would confirm, but replay uses the stored status.
    with start(street_graph, store, review_photo=reviewer(PhotoVerdict.CONFIRMED)) as restarted:
        listed = restarted.get("/reports").json()
        distance = shortest_distance(restarted)

    assert [(i["report_id"], i["verification"]) for i in listed] == [(report_id, "pending")]
    assert distance == pytest.approx(200.0)


def test_every_write_is_stored_with_provenance(street_graph):
    store = MemoryReportStore()
    with start(street_graph, store, reviewer(PhotoVerdict.REJECTED)) as client:
        report_id = report(client, user="alice", where=(42.35003, -71.1074)).json()["report_id"]
        vote(client, "C-D", "bob", blocked=False)

    photo, ballot = store.all()
    assert (photo.report_id, photo.segment_id, photo.user_id) == (report_id, "A-B", "alice")
    assert (photo.lat, photo.lon, photo.blocked) == (42.35003, -71.1074, True)
    assert (photo.status, photo.photo) == (PhotoVerdict.REJECTED, JPEG)
    assert photo.reported_at.tzinfo is not None
    assert (ballot.segment_id, ballot.user_id, ballot.blocked, ballot.status) == ("C-D", "bob", False, None)
    assert ballot.report_id.startswith("v_")


def test_refused_vote_is_not_stored(street_graph):
    store = MemoryReportStore()
    with start(street_graph, store) as client:
        for segment in ["A-B", "B-D", "A-C"]:
            vote(client, segment, "spammer", blocked=True)
        assert vote(client, "C-D", "spammer", blocked=True).json()["outcome"] == "photo_required"

    assert sorted(row.segment_id for row in store.all()) == ["A-B", "A-C", "B-D"]


def test_rejected_requests_are_not_stored(street_graph):
    store = MemoryReportStore()
    with start(street_graph, store, reviewer(PhotoVerdict.CONFIRMED)) as client:
        report(client, user=None)  # 401
        report(client, photo=b"GIF89a")  # 415
        vote(client, "A-B", "u1", blocked=True, where=NEAR["C-D"])  # 403

    assert store.all() == []


class FailingStore(MemoryReportStore):
    def add(self, row):
        raise ConnectionError("database is down")


def test_report_is_not_applied_when_the_store_fails(street_graph):
    with start(street_graph, FailingStore(), reviewer(PhotoVerdict.CONFIRMED)) as client:
        response = report(client)
        voted = vote(client, "A-B", "u1", blocked=True)
        distance = shortest_distance(client)
        listed = client.get("/reports").json()

    assert response.status_code == 503
    assert voted.status_code == 503
    assert "try again" in response.json()["detail"]
    assert distance == pytest.approx(200.0)
    assert listed == []


# --- Choosing the store --------------------------------------------------------------


def test_without_pghost_the_store_is_in_memory_with_a_warning(caplog):
    with caplog.at_level(logging.WARNING):
        store = storage.default_store()

    assert isinstance(store, MemoryReportStore)
    assert "PGHOST is not set" in caplog.text


def test_with_pghost_the_postgres_store_is_used_and_closed(street_graph, monkeypatch):
    opened = []

    class FakePostgresStore(MemoryReportStore):
        def __init__(self, conninfo=""):
            super().__init__()
            self.conninfo = conninfo
            self.closed = False
            opened.append(self)

        def close(self):
            self.closed = True

    monkeypatch.setenv("PGHOST", "db.example.invalid")
    monkeypatch.setattr(storage, "PostgresReportStore", FakePostgresStore)

    with TestClient(create_app(graph=street_graph)):
        pass

    [store] = opened
    assert store.conninfo == ""  # libpq reads the PG* variables itself
    assert store.closed  # closed on shutdown
