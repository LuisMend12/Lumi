import pytest
from shapely.geometry import LineString

from app.segments import SegmentIndex

# Midpoints of the test graph's segments (see conftest.py).
AB_MID = (42.3500, -71.1074)
CD_MID = (42.3495, -71.1062)


def test_nearest_segment_to_a_point_beside_a_street(street_graph):
    index = SegmentIndex(street_graph)

    # About 3 m north of the A-B street.
    segment_id, distance_m = index.nearest(42.35003, -71.1074)

    assert segment_id == "A-B"
    assert distance_m == pytest.approx(3.3, abs=0.5)


def test_nearest_uses_the_closest_point_on_the_segment_not_its_endpoints(street_graph):
    index = SegmentIndex(street_graph)

    # Halfway along C-D, nowhere near an intersection.
    segment_id, distance_m = index.nearest(*CD_MID)

    assert segment_id == "C-D"
    assert distance_m == pytest.approx(0.0, abs=0.5)


def test_distance_to_a_named_segment(street_graph):
    index = SegmentIndex(street_graph)

    # From C-D's midpoint to A-B: the closest point is B, about 74 m away.
    assert index.distance_m("A-B", *CD_MID) == pytest.approx(74, abs=2)


def test_segment_ids_cover_both_directions_once(street_graph):
    index = SegmentIndex(street_graph)

    assert sorted(index.ids()) == ["A-B", "A-C", "B-D", "C-D"]
    assert index.endpoints("A-B") == ("A", "B")


def test_unknown_segment_id_is_not_found(street_graph):
    index = SegmentIndex(street_graph)

    assert "A-D" not in index
    with pytest.raises(KeyError):
        index.endpoints("A-D")


def test_coordinates_and_midpoint(street_graph):
    index = SegmentIndex(street_graph)

    assert index.coordinates("A-B") == [(42.3500, -71.1080), (42.3500, -71.1068)]
    assert index.midpoint("A-B") == pytest.approx(AB_MID)


def test_curved_street_uses_its_stored_shape(street_graph):
    # Bend A-B far to the south, through (42.3480, -71.1074).
    bend = LineString([(-71.1080, 42.3500), (-71.1074, 42.3480), (-71.1068, 42.3500)])
    for u, v in [("A", "B"), ("B", "A")]:
        street_graph.edges[u, v]["geometry"] = bend
    index = SegmentIndex(street_graph)

    segment_id, distance_m = index.nearest(42.3480, -71.1074)

    assert segment_id == "A-B"
    assert distance_m == pytest.approx(0.0, abs=0.5)
    assert index.coordinates("A-B")[1] == (42.3480, -71.1074)


def test_segments_within_a_radius(street_graph):
    index = SegmentIndex(street_graph)

    nearby = index.within(*CD_MID, radius_m=60)

    # C-D runs through the point and B-D is 56 m north of it; A-B and A-C are about 74 m away.
    assert set(nearby) == {"C-D", "B-D"}
    assert nearby["C-D"] == pytest.approx(0.0, abs=0.5)
    assert nearby["B-D"] == pytest.approx(56, abs=1)
