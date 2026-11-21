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


def test_route_rejects_unknown_mode(client):
    response = client.get("/route", params={**A_TO_D, "mode": "fastest"})

    assert response.status_code == 422


def test_route_rejects_point_outside_coverage_area(client):
    far_away = {**A_TO_D, "end_lat": 42.3601, "end_lon": -71.0589}  # downtown Boston

    response = client.get("/route", params={**far_away, "mode": "shortest"})

    assert response.status_code == 422
    assert "outside" in response.json()["detail"]


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
