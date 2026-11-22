"""Download the walking network around BU from OpenStreetMap. Run once:

    uv run python scripts/build_graph.py

Stairs are kept as their own edges (#33). By default OSMnx merges a footway
and the few steps on it into one edge tagged ['footway', 'steps'], so
Accessible mode, which skips stairs, threw away whole paths. Simplifying with
edge_attrs_differ=["highway"] keeps a node wherever the highway tag changes.
"""

import sys
from pathlib import Path

import networkx as nx
import osmnx as ox

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import AREA_CENTER_LAT, AREA_CENTER_LON, AREA_RADIUS_M, GRAPH_PATH  # noqa: E402


def simplify_keeping_stairs(raw: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Merge plain path nodes, but never across a change of highway tag (e.g. footway -> steps)."""
    return ox.simplify_graph(raw, edge_attrs_differ=["highway"])


def mixed_stair_edges(graph: nx.MultiDiGraph) -> int:
    """Edges whose highway is a list that includes steps: these hide stairs inside a longer path."""
    return sum(
        1
        for _, _, highway in graph.edges(data="highway")
        if isinstance(highway, list) and "steps" in highway and len(highway) > 1
    )


def main() -> None:
    print(f"Downloading walk network: {AREA_RADIUS_M} m around ({AREA_CENTER_LAT}, {AREA_CENTER_LON})...")
    raw = ox.graph_from_point(
        (AREA_CENTER_LAT, AREA_CENTER_LON), dist=AREA_RADIUS_M, network_type="walk", simplify=False
    )
    graph = simplify_keeping_stairs(raw)
    GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    ox.save_graphml(graph, GRAPH_PATH)
    size_mb = GRAPH_PATH.stat().st_size / 1_000_000
    print(f"Saved {len(graph.nodes)} intersections, {len(graph.edges)} segments to {GRAPH_PATH} ({size_mb:.1f} MB)")
    print(f"Stair edges mixed with other path types: {mixed_stair_edges(graph)} (should be 0 or close)")


if __name__ == "__main__":
    main()
