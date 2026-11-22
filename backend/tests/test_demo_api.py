"""Demo mode (#38): simulated voters that only exist when LUMI_DEMO_MODE=1."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.reports import PhotoVerdict
from app.storage import MemoryReportStore
from tests.test_report_api import A_TO_D, NEAR, report, vote

SEGMENT = "A-B"


def confirm(photo: bytes) -> PhotoVerdict:
    return PhotoVerdict.CONFIRMED


@pytest.fixture
def store() -> MemoryReportStore:
    return MemoryReportStore()


@pytest.fixture
def demo(street_graph, store, monkeypatch):
    monkeypatch.setenv("LUMI_DEMO_MODE", "1")
    with TestClient(create_app(graph=street_graph, review_photo=confirm, store=store)) as client:
        yield client


def shortest_nodes_avoid_a_to_b(client: TestClient) -> bool:
    route = client.get("/route", params={**A_TO_D, "mode": "shortest"}).json()
    return route["distance_m"] == pytest.approx(300.0)  # the detour via C


@pytest.mark.parametrize(
    "method, path, body",
    [
        ("post", f"/demo/segments/{SEGMENT}/block", None),
        ("post", f"/demo/segments/{SEGMENT}/votes", {"blocked": True}),
        ("post", "/demo/reset", None),
    ],
)
def test_demo_endpoints_are_404_without_demo_mode(street_graph, monkeypatch, method, path, body):
    monkeypatch.delenv("LUMI_DEMO_MODE", raising=False)
    with TestClient(create_app(graph=street_graph, review_photo=confirm)) as client:
        response = getattr(client, method)(path, json=body)

    assert response.status_code == 404


def test_simulated_block_blocks_the_segment_and_is_labeled(demo, store):
    response = demo.post(f"/demo/segments/{SEGMENT}/block")

    assert response.status_code == 200
    assert response.json()["segment_status"] == "blocked"
    assert shortest_nodes_avoid_a_to_b(demo)
    [listed] = demo.get("/reports").json()
    assert listed["simulated"] is True
    assert [row.simulated for row in store.all()] == [True]


def test_four_simulated_unblocked_votes_reopen_a_blocked_segment(demo):
    demo.post(f"/demo/segments/{SEGMENT}/block")

    response = demo.post(f"/demo/segments/{SEGMENT}/votes", json={"blocked": False})

    assert response.status_code == 200
    assert response.json() == {"votes_cast": 4, "outcome": "status_changed", "segment_status": "open"}
    assert not shortest_nodes_avoid_a_to_b(demo)


def test_three_simulated_votes_do_not_flip(demo):
    demo.post(f"/demo/segments/{SEGMENT}/block")

    response = demo.post(f"/demo/segments/{SEGMENT}/votes", json={"blocked": False, "voters": 3})

    assert response.json() == {"votes_cast": 3, "outcome": "vote_recorded", "segment_status": "blocked"}


def test_simulated_votes_skip_the_nearby_check_and_user_header(demo):
    # No X-User-Id, and no location at all: simulated voters aren't real people.
    response = demo.post(f"/demo/segments/{SEGMENT}/votes", json={"blocked": True})

    assert response.status_code == 200
    assert response.json()["segment_status"] == "blocked"


def test_simulated_votes_on_an_unknown_segment_are_404(demo):
    response = demo.post("/demo/segments/no-such/votes", json={"blocked": True})

    assert response.status_code == 404


def test_voter_count_is_limited(demo):
    response = demo.post(f"/demo/segments/{SEGMENT}/votes", json={"blocked": True, "voters": 50})

    assert response.status_code == 422


def test_reset_removes_only_simulated_rows_and_rebuilds_status(demo, store):
    real = report(demo, user="alice", where=NEAR["C-D"])  # a real confirmed block on C-D
    assert real.json()["segment_status"] == "blocked"
    demo.post(f"/demo/segments/{SEGMENT}/block")
    demo.post(f"/demo/segments/{SEGMENT}/votes", json={"blocked": False, "voters": 2})

    response = demo.post("/demo/reset")

    assert response.status_code == 200
    assert response.json() == {"removed": 3}
    assert [row.simulated for row in store.all()] == [False]
    listed = demo.get("/reports").json()
    assert [item["segment_id"] for item in listed] == ["C-D"]
    assert all(item["simulated"] is False for item in listed)
    # A-B is open again (its only evidence was simulated); C-D stays blocked.
    route = demo.get("/route", params={**A_TO_D, "mode": "shortest"}).json()
    assert route["distance_m"] == pytest.approx(200.0)


def test_real_votes_still_need_a_user_and_nearby_check_in_demo_mode(demo):
    response = vote(demo, SEGMENT, user=None, blocked=True)

    assert response.status_code == 401


def test_demo_status_says_demo_mode_is_on(demo):
    assert demo.get("/demo/status").json() == {"demo_mode": True}


def test_demo_status_is_404_without_demo_mode(street_graph, monkeypatch):
    monkeypatch.delenv("LUMI_DEMO_MODE", raising=False)
    with TestClient(create_app(graph=street_graph, review_photo=confirm)) as client:
        assert client.get("/demo/status").status_code == 404


def test_nearest_segment_to_a_point_on_a_route(demo):
    lat, lon = NEAR["A-B"]

    response = demo.get("/demo/segments/nearest", params={"lat": lat, "lon": lon})

    assert response.status_code == 200
    body = response.json()
    assert body["segment_id"] == "A-B"
    assert body["distance_m"] < 5


def test_nearest_segment_outside_coverage_is_422(demo):
    response = demo.get("/demo/segments/nearest", params={"lat": 42.3601, "lon": -71.0589})  # downtown

    assert response.status_code == 422
