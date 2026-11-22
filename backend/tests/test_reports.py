from datetime import datetime, timedelta

import pytest

from app.reports import (
    PhotoVerdict,
    ReportOutcome,
    SegmentReports,
    SegmentStatus,
)
from app.routing import RouteMode, find_route, segment_key

AB = segment_key("A", "B")
PHOTO = b"fake-jpeg-bytes"
T0 = datetime(2026, 11, 21, 12, 0)


def reviewer(verdict: PhotoVerdict):
    """Fake photo agent that always returns the same verdict."""
    return lambda photo: verdict


def blocked_book() -> SegmentReports:
    book = SegmentReports(review_photo=reviewer(PhotoVerdict.CONFIRMED))
    book.report_blocked_with_photo(AB, "reporter", PHOTO, T0)
    return book


# --- Photo reports ---------------------------------------------------------


def test_confirmed_photo_report_blocks_segment():
    book = SegmentReports(review_photo=reviewer(PhotoVerdict.CONFIRMED))

    outcome = book.report_blocked_with_photo(AB, "alice", PHOTO, T0)

    assert outcome is ReportOutcome.STATUS_CHANGED
    assert book.status(AB) is SegmentStatus.BLOCKED


def test_rejected_photo_is_kept_as_unverified_and_does_not_block():
    book = SegmentReports(review_photo=reviewer(PhotoVerdict.REJECTED))

    outcome = book.report_blocked_with_photo(AB, "alice", PHOTO, T0)

    assert outcome is ReportOutcome.UNVERIFIED
    assert book.status(AB) is SegmentStatus.OPEN
    assert [(r.segment, r.verdict) for r in book.photo_reports()] == [(AB, PhotoVerdict.REJECTED)]


def test_agent_outage_keeps_report_pending_and_does_not_block():
    book = SegmentReports(review_photo=reviewer(PhotoVerdict.UNAVAILABLE))

    outcome = book.report_blocked_with_photo(AB, "alice", PHOTO, T0)

    assert outcome is ReportOutcome.PENDING
    assert book.status(AB) is SegmentStatus.OPEN
    assert [(r.segment, r.verdict) for r in book.photo_reports()] == [(AB, PhotoVerdict.UNAVAILABLE)]


def test_retrying_pending_report_blocks_once_agent_confirms():
    verdicts = iter([PhotoVerdict.UNAVAILABLE, PhotoVerdict.CONFIRMED])
    book = SegmentReports(review_photo=lambda photo: next(verdicts))
    book.report_blocked_with_photo(AB, "alice", PHOTO, T0)

    book.retry_pending()

    assert book.status(AB) is SegmentStatus.BLOCKED
    assert [r.verdict for r in book.photo_reports()] == [PhotoVerdict.CONFIRMED]


# --- One-tap votes ---------------------------------------------------------


def test_three_unblocked_votes_do_not_flip_a_blocked_segment():
    book = blocked_book()

    for user in ["u1", "u2", "u3"]:
        book.vote(AB, user, blocked=False, now=T0)

    assert book.status(AB) is SegmentStatus.BLOCKED


def test_fourth_distinct_user_flips_blocked_to_open():
    book = blocked_book()
    for user in ["u1", "u2", "u3"]:
        book.vote(AB, user, blocked=False, now=T0)

    outcome = book.vote(AB, "u4", blocked=False, now=T0)

    assert outcome is ReportOutcome.STATUS_CHANGED
    assert book.status(AB) is SegmentStatus.OPEN


def test_same_user_voting_repeatedly_counts_once():
    book = blocked_book()

    for _ in range(4):
        book.vote(AB, "u1", blocked=False, now=T0)

    assert book.status(AB) is SegmentStatus.BLOCKED


def test_user_changing_their_vote_only_keeps_the_latest():
    book = blocked_book()
    for user in ["u1", "u2", "u3"]:
        book.vote(AB, user, blocked=False, now=T0)

    book.vote(AB, "u1", blocked=True, now=T0)
    book.vote(AB, "u4", blocked=False, now=T0)

    assert book.status(AB) is SegmentStatus.BLOCKED


def test_four_distinct_blocked_votes_block_an_open_segment():
    book = SegmentReports(review_photo=reviewer(PhotoVerdict.CONFIRMED))

    for user in ["u1", "u2", "u3", "u4"]:
        book.vote(AB, user, blocked=True, now=T0)

    assert book.status(AB) is SegmentStatus.BLOCKED


def test_votes_before_a_status_change_do_not_carry_over():
    book = blocked_book()
    for user in ["u1", "u2", "u3", "u4"]:
        book.vote(AB, user, blocked=False, now=T0)  # flips to OPEN

    for user in ["u5", "u6", "u7"]:
        book.vote(AB, user, blocked=True, now=T0)

    assert book.status(AB) is SegmentStatus.OPEN


# --- Abuse rule ------------------------------------------------------------


def test_user_with_too_many_recent_block_reports_must_send_a_photo():
    book = SegmentReports(review_photo=reviewer(PhotoVerdict.CONFIRMED))
    for other in ["s1", "s2", "s3"]:
        book.vote(segment_key("X", other), "spammer", blocked=True, now=T0)

    outcome = book.vote(AB, "spammer", blocked=True, now=T0)

    assert outcome is ReportOutcome.PHOTO_REQUIRED


def test_photo_required_vote_is_not_counted():
    book = SegmentReports(review_photo=reviewer(PhotoVerdict.CONFIRMED))
    for other in ["s1", "s2", "s3"]:
        book.vote(segment_key("X", other), "spammer", blocked=True, now=T0)
    book.vote(AB, "spammer", blocked=True, now=T0)  # refused

    for user in ["u1", "u2", "u3"]:
        book.vote(AB, user, blocked=True, now=T0)

    assert book.status(AB) is SegmentStatus.OPEN


def test_block_reports_older_than_the_window_are_forgotten():
    book = SegmentReports(review_photo=reviewer(PhotoVerdict.CONFIRMED))
    for other in ["s1", "s2", "s3"]:
        book.vote(segment_key("X", other), "busy", blocked=True, now=T0)

    outcome = book.vote(AB, "busy", blocked=True, now=T0 + timedelta(hours=25))

    assert outcome is ReportOutcome.VOTE_RECORDED


def test_flagged_user_can_still_report_with_a_photo():
    book = SegmentReports(review_photo=reviewer(PhotoVerdict.CONFIRMED))
    for other in ["s1", "s2", "s3"]:
        book.vote(segment_key("X", other), "spammer", blocked=True, now=T0)

    outcome = book.report_blocked_with_photo(AB, "spammer", PHOTO, T0)

    assert outcome is ReportOutcome.STATUS_CHANGED


def test_unblocked_votes_are_never_limited():
    book = blocked_book()
    for other in ["s1", "s2", "s3"]:
        book.vote(segment_key("X", other), "helper", blocked=True, now=T0)

    outcome = book.vote(AB, "helper", blocked=False, now=T0)

    assert outcome is ReportOutcome.VOTE_RECORDED



def test_confirming_already_blocked_sidewalks_does_not_count_toward_the_limit():
    # #57: the limit is for people blocking sidewalks, not for people keeping the map current.
    book = SegmentReports(review_photo=reviewer(PhotoVerdict.CONFIRMED))
    blocked = [segment_key("X", other) for other in ["s1", "s2", "s3", "s4"]]
    for segment in blocked:
        book.report_blocked_with_photo(segment, "reporter", PHOTO, T0)

    outcomes = [book.vote(segment, "helper", blocked=True, now=T0) for segment in blocked]

    assert outcomes == [ReportOutcome.VOTE_RECORDED] * 4
    assert book.vote(AB, "helper", blocked=True, now=T0) is ReportOutcome.VOTE_RECORDED  # still under the limit


def test_user_over_the_limit_can_still_confirm_a_blocked_sidewalk():
    book = blocked_book()
    for other in ["s1", "s2", "s3"]:
        book.vote(segment_key("X", other), "busy", blocked=True, now=T0)

    assert book.vote_needs_photo(AB, "busy", blocked=True, now=T0) is False
    assert book.vote(AB, "busy", blocked=True, now=T0) is ReportOutcome.VOTE_RECORDED
    assert book.vote_needs_photo(segment_key("X", "s9"), "busy", blocked=True, now=T0) is True

# --- Routing integration ---------------------------------------------------


@pytest.mark.parametrize("mode", list(RouteMode))
def test_blocked_segment_changes_route_in_every_mode(street_graph, mode):
    book = blocked_book()

    route = find_route(street_graph, "A", "D", mode, book.hazards())

    assert route.nodes == ["A", "C", "D"]


def test_unverified_and_pending_reports_do_not_affect_routing(street_graph):
    book = SegmentReports(review_photo=reviewer(PhotoVerdict.REJECTED))
    book.report_blocked_with_photo(AB, "alice", PHOTO, T0)

    route = find_route(street_graph, "A", "D", RouteMode.SHORTEST, book.hazards())

    assert route.nodes == ["A", "B", "D"]


# --- What the API lists ----------------------------------------------------


def test_confirmed_reports_are_kept_with_their_id():
    book = SegmentReports(review_photo=reviewer(PhotoVerdict.CONFIRMED))

    book.report_blocked_with_photo(AB, "alice", PHOTO, T0, report_id="r_1")

    [report] = book.photo_reports()
    assert (report.report_id, report.segment, report.user_id) == ("r_1", AB, "alice")
    assert report.verdict is PhotoVerdict.CONFIRMED
    assert report.reported_at == T0
    assert report.photo == b""  # reviewed, so the photo isn't kept in memory


def test_report_gets_an_id_when_none_is_given():
    book = SegmentReports(review_photo=reviewer(PhotoVerdict.REJECTED))

    book.report_blocked_with_photo(AB, "alice", PHOTO, T0)

    [report] = book.photo_reports()
    assert report.report_id.startswith("r_")


def test_retried_report_moves_from_pending_to_confirmed():
    verdicts = iter([PhotoVerdict.UNAVAILABLE, PhotoVerdict.CONFIRMED])
    book = SegmentReports(review_photo=lambda photo: next(verdicts))
    book.report_blocked_with_photo(AB, "alice", PHOTO, T0, report_id="r_1")
    assert book.photo_reports()[0].photo == PHOTO  # pending keeps the photo to re-send it

    book.retry_pending()

    assert [(r.report_id, r.verdict, r.photo) for r in book.photo_reports()] == [("r_1", PhotoVerdict.CONFIRMED, b"")]


def test_known_verdict_skips_the_reviewer():
    def no_reviewer(photo):
        raise AssertionError("reviewer must not be called")

    book = SegmentReports(review_photo=no_reviewer)

    outcome = book.report_blocked_with_photo(AB, "alice", PHOTO, T0, verdict=PhotoVerdict.CONFIRMED)

    assert outcome is ReportOutcome.STATUS_CHANGED
    assert book.status(AB) is SegmentStatus.BLOCKED


def test_reported_segments_include_votes_and_every_kind_of_photo_report():
    verdicts = iter([PhotoVerdict.CONFIRMED, PhotoVerdict.REJECTED, PhotoVerdict.UNAVAILABLE])
    book = SegmentReports(review_photo=lambda photo: next(verdicts))
    for other in ["s1", "s2", "s3"]:
        book.report_blocked_with_photo(segment_key("X", other), "alice", PHOTO, T0)
    book.vote(AB, "bob", blocked=True, now=T0)

    assert book.reported_segments() == {segment_key("X", s) for s in ["s1", "s2", "s3"]} | {AB}


def test_user_needs_photo_matches_the_vote_rule():
    book = SegmentReports(review_photo=reviewer(PhotoVerdict.CONFIRMED))
    for other in ["s1", "s2"]:
        book.vote(segment_key("X", other), "busy", blocked=True, now=T0)
    assert not book.needs_photo("busy", T0)

    book.vote(segment_key("X", "s3"), "busy", blocked=True, now=T0)

    assert book.needs_photo("busy", T0)
    assert not book.needs_photo("busy", T0 + timedelta(hours=25))
