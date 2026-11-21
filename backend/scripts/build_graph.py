"""Download the walking network around BU from OpenStreetMap. Run once:

    uv run python scripts/build_graph.py
"""

import sys
from pathlib import Path

import osmnx as ox

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import AREA_CENTER_LAT, AREA_CENTER_LON, AREA_RADIUS_M, GRAPH_PATH  # noqa: E402


def main() -> None:
    print(f"Downloading walk network: {AREA_RADIUS_M} m around ({AREA_CENTER_LAT}, {AREA_CENTER_LON})...")
    graph = ox.graph_from_point(
        (AREA_CENTER_LAT, AREA_CENTER_LON), dist=AREA_RADIUS_M, network_type="walk"
    )
    GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    ox.save_graphml(graph, GRAPH_PATH)
    size_mb = GRAPH_PATH.stat().st_size / 1_000_000
    print(f"Saved {len(graph.nodes)} intersections, {len(graph.edges)} segments to {GRAPH_PATH} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
