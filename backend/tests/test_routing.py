import pytest
from shapely.geometry import LineString

from app.routing import (
    Hazard,
    NoRouteError,
    RouteHazard,
    RouteMode,
    find_route,
    nearest_node,
    segment_id,
    segment_key,
)


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
    [route_hazard] = route.hazards
    assert isinstance(route_hazard, RouteHazard)
    assert route_hazard.segment_id == "A-B"
    assert route_hazard.location == pytest.approx((42.3500, -71.1074))
    assert (route_hazard.kind, route_hazard.severity, route_hazard.blocked) == ("ice", 0.9, False)


def test_route_hazard_location_is_segment_midpoint_and_id_is_direction_free(street_graph):
    # Reported on B-D, walked B->D; the id still puts the smaller node first.
    hazards = hazards_on("D", "B", ICE)

    route = find_route(street_graph, "A", "D", RouteMode.SHORTEST, hazards)

    [route_hazard] = route.hazards
    assert route_hazard.segment_id == "B-D"
    assert route_hazard.location == pytest.approx((42.3500, -71.1062))
    assert route_hazard.kind == "ice"


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


def test_route_follows_curved_street_geometry(street_graph):
    # A->B bends south through a midpoint; OSM stores geometry as (lon, lat).
    street_graph.edges["A", "B"]["geometry"] = LineString([(-71.1080, 42.3500), (-71.1074, 42.3497), (-71.1068, 42.3500)])

    route = find_route(street_graph, "A", "D", RouteMode.SHORTEST, hazards={})

    assert route.coordinates == [
        (42.3500, -71.1080),
        (42.3497, -71.1074),
        (42.3500, -71.1068),
        (42.3500, -71.1056),
    ]


def test_curved_geometry_stored_backwards_is_reversed(street_graph):
    # Geometry drawn B->A on the A->B edge must still walk A->B.
    street_graph.edges["A", "B"]["geometry"] = LineString([(-71.1068, 42.3500), (-71.1074, 42.3497), (-71.1080, 42.3500)])

    route = find_route(street_graph, "A", "D", RouteMode.SHORTEST, hazards={})

    assert route.coordinates[:3] == [(42.3500, -71.1080), (42.3497, -71.1074), (42.3500, -71.1068)]


def test_every_mode_has_a_user_facing_description():
    for mode in RouteMode:
        assert len(mode.description) > 20


def test_nearest_node_snaps_point_and_reports_distance(street_graph):
    node, distance_m = nearest_node(street_graph, lat=42.34995, lon=-71.10795)

    assert node == "A"
    assert distance_m < 20


def test_segment_id_is_the_same_in_both_directions():
    assert segment_id("A", "B") == segment_id("B", "A") == "A-B"


def test_segment_id_sorts_osm_node_ids_as_numbers():
    # Real graph ids are ints: 9 < 10 numerically, though "10" < "9" as text.
    assert segment_id(10, 9) == segment_id(9, 10) == "9-10"
    assert segment_id(61340937, 61326726) == "61326726-61340937"
