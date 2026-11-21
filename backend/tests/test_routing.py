import pytest

from app.routing import Hazard, NoRouteError, RouteMode, find_route, nearest_node, segment_key


def hazards_on(u: str, v: str, *hazards: Hazard) -> dict:
    return {segment_key(u, v): list(hazards)}


ICE = Hazard(kind="ice", severity=0.9, blocked=False)
SNOWBANK = Hazard(kind="snowbank", severity=1.0, blocked=True)


def test_shortest_takes_direct_route_with_no_hazards(street_graph):
    route = find_route(street_graph, "A", "D", RouteMode.SHORTEST, hazards={})

    assert route.nodes == ["A", "B", "D"]
    assert route.distance_m == pytest.approx(200.0)
    assert route.hazards == []


def test_shortest_goes_through_ice_but_reports_it(street_graph):
    hazards = hazards_on("A", "B", ICE)

    route = find_route(street_graph, "A", "D", RouteMode.SHORTEST, hazards)

    assert route.nodes == ["A", "B", "D"]
    assert route.hazards == [ICE]


def test_safer_detours_around_ice(street_graph):
    hazards = hazards_on("A", "B", ICE)

    route = find_route(street_graph, "A", "D", RouteMode.SAFER, hazards)

    assert route.nodes == ["A", "C", "D"]
    assert route.distance_m == pytest.approx(300.0)
    assert route.hazards == []


@pytest.mark.parametrize("mode", list(RouteMode))
def test_every_mode_skips_a_blocked_segment(street_graph, mode):
    hazards = hazards_on("A", "B", SNOWBANK)

    route = find_route(street_graph, "A", "D", mode, hazards)

    assert route.nodes == ["A", "C", "D"]


def test_hazard_applies_in_both_directions(street_graph):
    # Reported while walking B->A; must still block A->B.
    hazards = hazards_on("B", "A", SNOWBANK)

    route = find_route(street_graph, "A", "D", RouteMode.SHORTEST, hazards)

    assert route.nodes == ["A", "C", "D"]


def test_no_route_when_every_path_is_blocked(street_graph):
    hazards = {
        segment_key("A", "B"): [SNOWBANK],
        segment_key("A", "C"): [SNOWBANK],
    }

    with pytest.raises(NoRouteError):
        find_route(street_graph, "A", "D", RouteMode.SHORTEST, hazards)


def test_route_includes_coordinates_in_order(street_graph):
    route = find_route(street_graph, "A", "D", RouteMode.SHORTEST, hazards={})

    assert route.coordinates == [(42.3500, -71.1080), (42.3500, -71.1068), (42.3500, -71.1056)]


def test_every_mode_has_a_user_facing_description():
    for mode in RouteMode:
        assert len(mode.description) > 20


def test_nearest_node_snaps_point_and_reports_distance(street_graph):
    node, distance_m = nearest_node(street_graph, lat=42.34995, lon=-71.10795)

    assert node == "A"
    assert distance_m < 20
