"""Risk-aware pedestrian routing (design option A).

The street graph is never modified. Hazard reports live in a separate
dict, and a weight function combines the two on every route request.
"""

from collections.abc import Callable, Hashable
from dataclasses import asdict, dataclass
from enum import Enum

import networkx as nx
import numpy as np

from app.config import SAFER_RISK_WEIGHT

EARTH_RADIUS_M = 6_371_000

SegmentKey = frozenset
Hazards = dict[SegmentKey, list["Hazard"]]


class RouteMode(str, Enum):
    SHORTEST = "shortest"
    SAFER = "safer"
    ACCESSIBLE = "accessible"

    @property
    def description(self) -> str:
        return _MODE_DESCRIPTIONS[self]


_MODE_DESCRIPTIONS = {
    RouteMode.SHORTEST: (
        "Shortest: the most direct walk. Skips sidewalks reported fully blocked, "
        "but may pass reported snow or ice. Check the warnings along the route."
    ),
    RouteMode.SAFER: (
        "Safer: detours around reported snow, ice, and obstructions when a "
        "reasonable alternative exists. Based on community reports, which can be "
        "incomplete. Not a guarantee that the route is safe."
    ),
    RouteMode.ACCESSIBLE: (
        "Accessible: skips sidewalks reported fully blocked and avoids reported "
        "hazards. Curb ramp and slope data is not included yet, so confirm the "
        "route before relying on it."
    ),
}


@dataclass(frozen=True)
class Hazard:
    kind: str
    severity: float  # 0.0 (minor) to 1.0 (severe)
    blocked: bool  # True = nobody can pass; every mode skips the segment

    def __post_init__(self) -> None:
        # Written so NaN fails too: every comparison with NaN is False.
        if not 0 <= self.severity <= 1:
            raise ValueError(f"Hazard severity must be between 0 and 1, got {self.severity!r}")


@dataclass(frozen=True)
class Route:
    nodes: list[Hashable]
    coordinates: list[tuple[float, float]]  # (lat, lon) in walking order
    distance_m: float
    hazards: list["RouteHazard"]  # hazards on segments the route still uses, in walking order


@dataclass(frozen=True)
class RouteHazard(Hazard):
    """A hazard on a segment the route uses, plus where it is. /route returns these as-is."""

    location: tuple[float, float]  # (lat, lon) segment midpoint, where the warning goes on the map


class NoRouteError(Exception):
    """No path exists that avoids every blocked segment."""


def segment_key(u: Hashable, v: Hashable) -> SegmentKey:
    """Same key for both walking directions of a sidewalk segment."""
    return frozenset((u, v))


def segment_id(u: Hashable, v: Hashable) -> str:
    """Public id of a sidewalk segment: "<u>-<v>" with the smaller node id first.

    Both walking directions share one id. Node ids are compared as values, so
    OSM's int ids sort numerically (9 before 10), and the test graph's strings
    sort alphabetically.
    """
    first, second = (u, v) if u <= v else (v, u)
    return f"{first}-{second}"


def _risk(hazards: list[Hazard]) -> float:
    return max((hazard.severity for hazard in hazards), default=0.0)


def _is_stairs(edge: dict) -> bool:
    """OSMnx stores `highway` as a string, or a list when merged ways had different tags."""
    highway = edge.get("highway")
    if isinstance(highway, list):
        return "steps" in highway
    return highway == "steps"


def make_weight(mode: RouteMode, hazards: Hazards) -> Callable[[Hashable, Hashable, dict], float | None]:
    """Build the per-request cost function. Returning None makes NetworkX skip the edge."""

    def weight(u: Hashable, v: Hashable, edge: dict) -> float | None:
        if mode is RouteMode.ACCESSIBLE and _is_stairs(edge):
            return None
        segment_hazards = hazards.get(segment_key(u, v), [])
        if any(hazard.blocked for hazard in segment_hazards):
            return None
        length = edge["length"]
        if mode is RouteMode.SHORTEST:
            return length
        return length * (1 + SAFER_RISK_WEIGHT * _risk(segment_hazards))

    return weight


def find_route(
    graph: nx.DiGraph, start: Hashable, end: Hashable, mode: RouteMode, hazards: Hazards
) -> Route:
    try:
        nodes = nx.dijkstra_path(graph, start, end, weight=make_weight(mode, hazards))
    except nx.NetworkXNoPath as error:
        if mode is RouteMode.ACCESSIBLE:  # Accessible also skips stairs, so say so (#33)
            message = "No step-free route found: every way between these points uses stairs or a blocked sidewalk."
        else:
            message = "No route found: every way between these points uses a blocked sidewalk."
        raise NoRouteError(message) from error

    segments = list(zip(nodes, nodes[1:]))
    coordinates = [_lat_lon(graph, nodes[0])]
    for u, v in segments:
        coordinates.extend(_segment_shape(graph, u, v)[1:])
    return Route(
        nodes=nodes,
        coordinates=coordinates,
        distance_m=sum(graph.edges[u, v]["length"] for u, v in segments),
        hazards=[
            RouteHazard(**asdict(h), location=_midpoint(graph, u, v))
            for u, v in segments
            for h in hazards.get(segment_key(u, v), [])
        ],
    )


def _midpoint(graph: nx.DiGraph, u: Hashable, v: Hashable) -> tuple[float, float]:
    (lat_u, lon_u), (lat_v, lon_v) = _lat_lon(graph, u), _lat_lon(graph, v)
    # 7 decimals is about 1 cm; it drops float noise like -71.10740000000001.
    return (round((lat_u + lat_v) / 2, 7), round((lon_u + lon_v) / 2, 7))


def _lat_lon(graph: nx.DiGraph, node: Hashable) -> tuple[float, float]:
    return (graph.nodes[node]["y"], graph.nodes[node]["x"])


def _segment_shape(graph: nx.DiGraph, u: Hashable, v: Hashable) -> list[tuple[float, float]]:
    """Points along the street from u to v; curved if OSM stored the shape."""
    geometry = graph.edges[u, v].get("geometry")
    if geometry is None:
        return [_lat_lon(graph, u), _lat_lon(graph, v)]
    points = [(lat, lon) for lon, lat in geometry.coords]
    start = _lat_lon(graph, u)
    if _squared_gap(points[-1], start) < _squared_gap(points[0], start):
        points.reverse()
    return points


def _squared_gap(a: tuple[float, float], b: tuple[float, float]) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def nearest_node(graph: nx.DiGraph, lat: float, lon: float) -> tuple[Hashable, float]:
    """Closest intersection to a point, and its distance in meters (haversine)."""
    node_ids = list(graph.nodes)
    lats = np.radians([graph.nodes[n]["y"] for n in node_ids])
    lons = np.radians([graph.nodes[n]["x"] for n in node_ids])
    lat0, lon0 = np.radians(lat), np.radians(lon)
    a = np.sin((lats - lat0) / 2) ** 2 + np.cos(lat0) * np.cos(lats) * np.sin((lons - lon0) / 2) ** 2
    distances = 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(a))
    index = int(np.argmin(distances))
    return node_ids[index], float(distances[index])
