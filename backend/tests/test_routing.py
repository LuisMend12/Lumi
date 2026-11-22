import pytest
from shapely.geometry import LineString

from app.routing import (
    Hazard,
    NoRouteError,
    RouteHazard,
    RouteMode,
    find_route,
    nearest_node,
    nearest_step_free,
    segment_id,
    segment_key,
    step_free_components,
    step_free_network,
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
    assert route_hazard.location == pytest.approx((42.3500, -71.1074))
    assert (route_hazard.kind, route_hazard.severity, route_hazard.blocked) == ("ice", 0.9, False)


def test_route_hazard_location_is_segment_midpoint_in_either_direction(street_graph):
    # Reported as D-B, walked B->D.
    hazards = hazards_on("D", "B", ICE)

    route = find_route(street_graph, "A", "D", RouteMode.SHORTEST, hazards)

    [route_hazard] = route.hazards
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


def add_stairs(graph, u: str, v: str, length: float, highway="steps") -> None:
    """Add a staircase between u and v, walkable in both directions."""
    graph.add_edge(u, v, length=length, highway=highway)
    graph.add_edge(v, u, length=length, highway=highway)


def test_shortest_takes_a_stairs_shortcut(street_graph):
    add_stairs(street_graph, "A", "D", 50.0)

    route = find_route(street_graph, "A", "D", RouteMode.SHORTEST, hazards={})

    assert route.nodes == ["A", "D"]


def test_safer_takes_a_stairs_shortcut(street_graph):
    add_stairs(street_graph, "A", "D", 50.0)

    route = find_route(street_graph, "A", "D", RouteMode.SAFER, hazards={})

    assert route.nodes == ["A", "D"]


def test_accessible_avoids_a_stairs_shortcut(street_graph):
    add_stairs(street_graph, "A", "D", 50.0)

    route = find_route(street_graph, "A", "D", RouteMode.ACCESSIBLE, hazards={})

    assert route.nodes == ["A", "B", "D"]


def test_accessible_avoids_stairs_tagged_as_a_list(street_graph):
    # OSMnx stores a list when a simplified edge merged ways with different tags.
    add_stairs(street_graph, "A", "D", 50.0, highway=["footway", "steps"])

    route = find_route(street_graph, "A", "D", RouteMode.ACCESSIBLE, hazards={})

    assert route.nodes == ["A", "B", "D"]


def test_accessible_uses_edges_with_other_highway_tags(street_graph):
    add_stairs(street_graph, "A", "D", 50.0, highway=["footway", "residential"])

    route = find_route(street_graph, "A", "D", RouteMode.ACCESSIBLE, hazards={})

    assert route.nodes == ["A", "D"]


def test_accessible_has_no_route_when_only_stairs_connect(street_graph):
    # Both ways out of A are staircases.
    add_stairs(street_graph, "A", "B", 100.0)
    add_stairs(street_graph, "A", "C", 150.0)

    with pytest.raises(NoRouteError):
        find_route(street_graph, "A", "D", RouteMode.ACCESSIBLE, hazards={})


def test_accessible_no_route_message_says_step_free(street_graph):
    add_stairs(street_graph, "A", "B", 100.0)
    add_stairs(street_graph, "A", "C", 150.0)

    with pytest.raises(NoRouteError) as raised:
        find_route(street_graph, "A", "D", RouteMode.ACCESSIBLE, hazards={})

    assert str(raised.value) == (
        "No step-free route found: every way between these points uses stairs or a blocked sidewalk."
    )


def test_no_route_message_is_readable_and_has_no_node_ids(street_graph):
    hazards = {segment_key("A", "B"): [SNOWBANK], segment_key("A", "C"): [SNOWBANK]}

    with pytest.raises(NoRouteError) as raised:
        find_route(street_graph, "A", "D", RouteMode.SAFER, hazards)

    assert str(raised.value) == "No route found: every way between these points uses a blocked sidewalk."


# --- Step-free snapping (#33) ---------------------------------------------------

def add_stairs_only_spot(graph, node: str, lat: float, lon: float, via: str = "A") -> None:
    """A spot reachable only by a staircase from `via`, like GSU's plaza in the real map."""
    graph.add_node(node, y=lat, x=lon)
    add_stairs(graph, via, node, 30.0)


def test_step_free_network_excludes_spots_reached_only_by_stairs(street_graph):
    add_stairs_only_spot(street_graph, "E", 42.35025, -71.1080)

    network = step_free_network(street_graph)

    assert network == {"A", "B", "C", "D"}


def test_spot_in_the_step_free_network_needs_no_snap(street_graph):
    network = step_free_network(street_graph)

    assert nearest_step_free(street_graph, "A", network) == ("A", 0.0)


def test_stairs_only_spot_snaps_to_the_nearest_step_free_point(street_graph):
    add_stairs_only_spot(street_graph, "E", 42.35025, -71.1080)  # about 28 m north of A
    network = step_free_network(street_graph)

    node, distance_m = nearest_step_free(street_graph, "E", network)

    assert node == "A"
    assert 25 < distance_m < 31


def add_step_free_island(graph) -> None:
    """E and F: a two-node plaza joined by a step-free path, reachable from A only by stairs."""
    add_stairs_only_spot(graph, "E", 42.35025, -71.1080)
    graph.add_node("F", y=42.35025, x=-71.1077)  # about 25 m east of E
    for u, v in [("E", "F"), ("F", "E")]:
        graph.add_edge(u, v, length=25.0, highway="footway")


def test_step_free_components_group_an_island_apart_from_the_main_network(street_graph):
    add_step_free_island(street_graph)

    groups = step_free_components(street_graph)

    assert groups["E"] == groups["F"]  # a step-free path joins them
    assert groups["E"] != groups["A"]
    assert {node for node, group in groups.items() if group == 0} == {"A", "B", "C", "D"}
    assert step_free_network(street_graph) == {"A", "B", "C", "D"}
