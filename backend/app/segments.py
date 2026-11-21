"""Find sidewalk segments by id or by location.

Built once at startup from the street graph, which never changes. Each segment
is stored as the straight pieces of its shape (curved streets have several),
so "nearest segment" means the closest point on the street itself, not the
closest intersection.
"""

from collections.abc import Hashable, Iterator

import networkx as nx
import numpy as np

from app.routing import EARTH_RADIUS_M, _midpoint, _segment_shape, segment_id


class SegmentIndex:
    def __init__(self, graph: nx.DiGraph) -> None:
        self._endpoints: dict[str, tuple[Hashable, Hashable]] = {}
        self._coordinates: dict[str, list[tuple[float, float]]] = {}
        self._midpoints: dict[str, tuple[float, float]] = {}
        for a, b in graph.edges:
            sid = segment_id(a, b)
            if sid in self._endpoints:
                continue  # the other walking direction of a segment we have
            u, v = (a, b) if a <= b else (b, a)
            shape = _segment_shape(graph, a, b)
            self._endpoints[sid] = (u, v)
            self._coordinates[sid] = shape if a == u else shape[::-1]
            self._midpoints[sid] = _midpoint(graph, u, v)

        self._ids = list(self._endpoints)
        self._position = {sid: i for i, sid in enumerate(self._ids)}
        # One row per straight piece, grouped by segment so np.minimum.reduceat
        # can take the closest piece of each segment.
        starts, ends, first_piece = [], [], []
        for sid in self._ids:
            points = self._coordinates[sid]
            first_piece.append(len(starts))
            starts.extend(points[:-1])
            ends.extend(points[1:])
        self._starts = np.radians(np.array(starts, dtype=float).reshape(-1, 2))
        self._ends = np.radians(np.array(ends, dtype=float).reshape(-1, 2))
        self._first_piece = np.array(first_piece, dtype=np.intp)

    def __contains__(self, sid: object) -> bool:
        return sid in self._endpoints

    def ids(self) -> Iterator[str]:
        return iter(self._ids)

    def endpoints(self, sid: str) -> tuple[Hashable, Hashable]:
        """(u, v) node ids, smaller first. KeyError if the segment doesn't exist."""
        return self._endpoints[sid]

    def coordinates(self, sid: str) -> list[tuple[float, float]]:
        """(lat, lon) points along the segment, from u to v."""
        return list(self._coordinates[sid])

    def midpoint(self, sid: str) -> tuple[float, float]:
        """(lat, lon) between the two intersections, as /route hazards use."""
        return self._midpoints[sid]

    def nearest(self, lat: float, lon: float) -> tuple[str, float]:
        """Closest segment to a point, and the distance to it in meters."""
        distances = self._segment_distances(lat, lon)
        index = int(np.argmin(distances))
        return self._ids[index], float(distances[index])

    def within(self, lat: float, lon: float, radius_m: float) -> dict[str, float]:
        """Segments within radius_m of a point, mapped to their distance in meters."""
        distances = self._segment_distances(lat, lon)
        return {self._ids[i]: float(distances[i]) for i in np.flatnonzero(distances <= radius_m)}

    def distance_m(self, sid: str, lat: float, lon: float) -> float:
        """Meters from a point to a segment. KeyError if the segment doesn't exist."""
        return float(self._segment_distances(lat, lon)[self._position[sid]])

    def _segment_distances(self, lat: float, lon: float) -> np.ndarray:
        """Point-to-segment distance for every segment, in meters.

        Uses an equirectangular projection centred on the point: within a few
        km the error is far below GPS noise, and it is one vectorized pass.
        """
        lat0, lon0 = np.radians(lat), np.radians(lon)
        scale = np.array([EARTH_RADIUS_M, EARTH_RADIUS_M * np.cos(lat0)])
        a = (self._starts - (lat0, lon0)) * scale  # piece start, meters from the point
        b = (self._ends - (lat0, lon0)) * scale
        ab = b - a
        length_sq = np.einsum("ij,ij->i", ab, ab)
        # Position of the closest point along each piece, clamped to the piece.
        with np.errstate(invalid="ignore", divide="ignore"):
            t = np.where(length_sq > 0, -np.einsum("ij,ij->i", a, ab) / length_sq, 0.0)
        closest = a + np.clip(t, 0.0, 1.0)[:, None] * ab
        piece_distances = np.hypot(closest[:, 0], closest[:, 1])
        return np.minimum.reduceat(piece_distances, self._first_piece)
