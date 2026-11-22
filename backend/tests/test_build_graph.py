"""scripts/build_graph.py (#33): simplifying the walk network must keep stairs as their own edges."""

import importlib.util
from pathlib import Path

import networkx as nx
import osmnx as ox

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_graph.py"
spec = importlib.util.spec_from_file_location("build_graph", SCRIPT)
build_graph = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_graph)


def raw_path() -> nx.MultiDiGraph:
    """An unsimplified OSM-like path 1-2-3-4: footway, footway, then a short staircase."""
    graph = nx.MultiDiGraph(crs="epsg:4326")
    for node, lon in [(1, -71.1000), (2, -71.0999), (3, -71.0998), (4, -71.0997)]:
        graph.add_node(node, x=lon, y=42.35, street_count=1)
    for (u, v), (osmid, highway) in {(1, 2): (10, "footway"), (2, 3): (10, "footway"), (3, 4): (11, "steps")}.items():
        for a, b in [(u, v), (v, u)]:
            graph.add_edge(a, b, osmid=osmid, highway=highway, length=8.0, oneway=False, reversed=a > b)
    return graph


def highways(graph: nx.MultiDiGraph) -> set:
    return {tuple(h) if isinstance(h, list) else h for _, _, h in graph.edges(data="highway")}


def test_default_simplification_merges_stairs_into_the_path():
    # The bug behind #33: one merged edge tagged ['footway', 'steps'].
    merged = ox.simplify_graph(raw_path())

    assert any(isinstance(h, tuple) and "steps" in h for h in highways(merged))


def test_build_graph_keeps_stairs_as_their_own_edges():
    simplified = build_graph.simplify_keeping_stairs(raw_path())

    assert highways(simplified) == {"footway", "steps"}
    assert 3 in simplified.nodes  # where the path turns into stairs
    assert 2 not in simplified.nodes  # plain footway nodes are still merged away


def test_stair_edges_that_mix_tags_are_counted():
    assert build_graph.mixed_stair_edges(ox.simplify_graph(raw_path())) == 2  # both directions
    assert build_graph.mixed_stair_edges(build_graph.simplify_keeping_stairs(raw_path())) == 0
