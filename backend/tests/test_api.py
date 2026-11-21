from fastapi.testclient import TestClient
import pytest

from app.main import create_app
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
