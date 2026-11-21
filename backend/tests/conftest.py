"""Shared test fixtures: a tiny fake street network near BU.

Layout (two ways from A to D):

    A ──100m── B ──100m── D      direct route, 200 m
     \                   /
      150m── C ──150m───         detour, 300 m

Every street is walkable in both directions, like a real sidewalk graph.
"""

import networkx as nx
import pytest

# Node id -> (lat, lon). Spread a few hundred meters apart near Marsh Plaza.
NODES = {
    "A": (42.3500, -71.1080),
    "B": (42.3500, -71.1068),
    "C": (42.3490, -71.1068),
    "D": (42.3500, -71.1056),
}

STREETS = [("A", "B", 100.0), ("B", "D", 100.0), ("A", "C", 150.0), ("C", "D", 150.0)]


@pytest.fixture
def street_graph() -> nx.DiGraph:
    graph = nx.DiGraph()
    for node_id, (lat, lon) in NODES.items():
        graph.add_node(node_id, y=lat, x=lon)
    for u, v, length in STREETS:
        graph.add_edge(u, v, length=length)
        graph.add_edge(v, u, length=length)
    return graph


@pytest.fixture(autouse=True)
def no_real_database(monkeypatch):
    """Keep create_app() on the in-memory store even if PGHOST is set in the shell.

    Postgres tests opt in with LUMI_TEST_DATABASE_URL instead (see test_storage.py).
    """
    monkeypatch.delenv("PGHOST", raising=False)
