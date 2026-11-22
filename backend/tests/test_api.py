from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from tests.conftest import auth_header
from app.routing import Hazard, segment_key


@pytest.fixture
def client(street_graph):
    app = create_app(graph=street_graph)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def blocked_client(street_graph):
    hazards = {segment_key("A", "B"): [Hazard(kind="snowbank", severity=1.0, blocked=True)]}
    app = create_app(graph=street_graph, hazards=hazards)
    with TestClient(app) as test_client:
        yield test_client


A_TO_D = {"start_lat": 42.3500, "start_lon": -71.1080, "end_lat": 42.3500, "end_lon": -71.1056}


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_route_returns_path_distance_and_mode_description(client):
    response = client.get("/route", params={**A_TO_D, "mode": "shortest"})

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "shortest"
    assert body["distance_m"] == pytest.approx(200.0)
    assert len(body["coordinates"]) == 3
    assert body["hazards"] == []
    assert "Shortest" in body["mode_description"]


def test_route_avoids_blocked_segment(blocked_client):
    response = blocked_client.get("/route", params={**A_TO_D, "mode": "shortest"})

    assert response.status_code == 200
    assert response.json()["distance_m"] == pytest.approx(300.0)


def test_frontend_origin_is_allowed_by_cors(client):
    response = client.get("/health", headers={"Origin": "http://localhost:3000"})

    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_route_rejects_unknown_mode(client):
    response = client.get("/route", params={**A_TO_D, "mode": "fastest"})

    assert response.status_code == 422


def test_route_rejects_point_outside_coverage_area(client):
    far_away = {**A_TO_D, "end_lat": 42.3601, "end_lon": -71.0589}  # downtown Boston

    response = client.get("/route", params={**far_away, "mode": "shortest"})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "outside" in detail
    assert "nearest mapped intersection" in detail


def test_route_rejects_invalid_latitude(client):
    response = client.get("/route", params={**A_TO_D, "start_lat": 123, "mode": "shortest"})

    assert response.status_code == 422


def test_validation_error_detail_is_one_readable_string(client):
    response = client.get("/route", params={**A_TO_D, "start_lat": 123, "mode": "shortest"})

    assert response.status_code == 422
    assert response.json()["detail"] == "start_lat: Input should be less than or equal to 90"


def test_validation_errors_for_several_fields_are_joined(client):
    params = {"start_lat": 123, "end_lat": 42.35, "end_lon": -71.1}  # start_lon missing

    response = client.get("/route", params=params)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, str)
    assert "start_lat: Input should be less than or equal to 90" in detail
    assert "start_lon: Field required" in detail


def test_invalid_vote_body_detail_is_a_string(client):
    response = client.post(
        "/segments/A-B/votes", json={"blocked": True, "lat": 999, "lon": -71.1}, headers=auth_header("alice")
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "lat: Input should be less than or equal to 90"


def test_route_returns_404_when_no_path_exists(street_graph):
    blocked = Hazard(kind="snowbank", severity=1.0, blocked=True)
    hazards = {segment_key("A", "B"): [blocked], segment_key("A", "C"): [blocked]}
    app = create_app(graph=street_graph, hazards=hazards)

    with TestClient(app) as test_client:
        response = test_client.get("/route", params={**A_TO_D, "mode": "safer"})

    assert response.status_code == 404


def test_route_returns_snapped_start_and_end(client):
    # Tapped points a little off A and D; the route starts and ends at those intersections.
    tapped = {"start_lat": 42.34995, "start_lon": -71.10795, "end_lat": 42.35005, "end_lon": -71.10565}

    response = client.get("/route", params={**tapped, "mode": "shortest"})

    assert response.status_code == 200
    body = response.json()
    assert body["snapped_start"] == [42.3500, -71.1080]
    assert body["snapped_end"] == [42.3500, -71.1056]
    assert body["coordinates"][0] == body["snapped_start"]
    assert body["coordinates"][-1] == body["snapped_end"]


def test_route_rejects_points_that_snap_to_the_same_intersection(client):
    # Both points are a few meters from A.
    near_a = {"start_lat": 42.34995, "start_lon": -71.10795, "end_lat": 42.35005, "end_lon": -71.10805}

    response = client.get("/route", params={**near_a, "mode": "safer"})

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Start and destination are too close to route between. Pick points farther apart."
    )


def test_route_hazard_has_location_kind_severity_and_blocked(street_graph):
    hazards = {segment_key("B", "A"): [Hazard(kind="ice", severity=0.6, blocked=False)]}
    app = create_app(graph=street_graph, hazards=hazards)

    with TestClient(app) as test_client:
        response = test_client.get("/route", params={**A_TO_D, "mode": "shortest"})

    assert response.status_code == 200
    [hazard] = response.json()["hazards"]
    assert hazard == {
        "location": pytest.approx([42.3500, -71.1074]),
        "kind": "ice",
        "severity": 0.6,
        "blocked": False,
    }


# --- Accessible step-free snapping (#33) ----------------------------------------

def stairs_only_spot(street_graph, lat: float, lon: float) -> None:
    """Spot E, reachable from A only by a staircase."""
    street_graph.add_node("E", y=lat, x=lon)
    for u, v in [("A", "E"), ("E", "A")]:
        street_graph.add_edge(u, v, length=30.0, highway="steps")


E_TO_D = {"start_lat": 42.35025, "start_lon": -71.1080, "end_lat": 42.3500, "end_lon": -71.1056}


def test_accessible_start_reachable_only_by_stairs_snaps_and_says_so(street_graph):
    stairs_only_spot(street_graph, 42.35025, -71.1080)  # ~28 m north of A
    with TestClient(create_app(graph=street_graph)) as client:
        response = client.get("/route", params={**E_TO_D, "mode": "accessible"})

    assert response.status_code == 200
    body = response.json()
    assert body["snapped_start"] == [42.3500, -71.1080]  # A, not E
    assert body["notice"] == "Your start is only reachable by stairs, so the step-free route starts 28 m away."


def test_accessible_destination_reachable_only_by_stairs_snaps_and_says_so(street_graph):
    stairs_only_spot(street_graph, 42.35025, -71.1080)
    d_to_e = {"start_lat": 42.3500, "start_lon": -71.1056, "end_lat": 42.35025, "end_lon": -71.1080}
    with TestClient(create_app(graph=street_graph)) as client:
        body = client.get("/route", params={**d_to_e, "mode": "accessible"}).json()

    assert body["snapped_end"] == [42.3500, -71.1080]
    assert body["notice"] == "Your destination is only reachable by stairs, so the step-free route ends 28 m away."


def test_accessible_does_not_snap_farther_than_100_m(street_graph):
    stairs_only_spot(street_graph, 42.3515, -71.1080)  # ~167 m north of A
    far = {**E_TO_D, "start_lat": 42.3515}
    with TestClient(create_app(graph=street_graph)) as client:
        response = client.get("/route", params={**far, "mode": "accessible"})

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "No step-free route found: your start is only reachable by stairs, "
        "and the nearest step-free point is 167 m away."
    )


def test_shortest_uses_stairs_and_does_not_snap(street_graph):
    stairs_only_spot(street_graph, 42.35025, -71.1080)
    with TestClient(create_app(graph=street_graph)) as client:
        body = client.get("/route", params={**E_TO_D, "mode": "shortest"}).json()

    assert body["snapped_start"] == [42.35025, -71.1080]  # E itself
    assert body["notice"] is None


def test_accessible_route_without_stairs_has_no_notice(client):
    body = client.get("/route", params={**A_TO_D, "mode": "accessible"}).json()

    assert body["notice"] is None


def step_free_island(street_graph) -> None:
    """E and F: a two-node plaza joined by a step-free path; only stairs lead from A to E."""
    stairs_only_spot(street_graph, 42.35025, -71.1080)
    street_graph.add_node("F", y=42.35025, x=-71.1077)  # about 25 m east of E
    for u, v in [("E", "F"), ("F", "E")]:
        street_graph.add_edge(u, v, length=25.0, highway="footway")


def test_accessible_route_inside_a_step_free_island_does_not_snap(street_graph):
    step_free_island(street_graph)
    e_to_f = {"start_lat": 42.35025, "start_lon": -71.1080, "end_lat": 42.35025, "end_lon": -71.1077}
    with TestClient(create_app(graph=street_graph)) as client:
        response = client.get("/route", params={**e_to_f, "mode": "accessible"})

    assert response.status_code == 200
    body = response.json()
    assert body["distance_m"] == 25.0  # E to F directly, no stairs
    assert body["snapped_start"] == [42.35025, -71.1080]
    assert body["snapped_end"] == [42.35025, -71.1077]
    assert body["notice"] is None


def test_accessible_from_an_island_to_the_main_network_snaps_only_the_island_end(street_graph):
    step_free_island(street_graph)
    f_to_d = {"start_lat": 42.35025, "start_lon": -71.1077, "end_lat": 42.3500, "end_lon": -71.1056}
    with TestClient(create_app(graph=street_graph)) as client:
        body = client.get("/route", params={**f_to_d, "mode": "accessible"}).json()

    assert body["snapped_start"] == [42.3500, -71.1080]  # F moved to A, the nearest step-free point
    assert body["snapped_end"] == [42.3500, -71.1056]  # D is already step-free
    assert body["notice"].startswith("Your start is only reachable by stairs")
    assert "destination" not in body["notice"]
