"""Community reports that decide whether a sidewalk segment is blocked.

Rules (team decisions):
- A "blocked" report with a photo counts only if the photo agent confirms it;
  a confirmed photo report blocks the segment right away.
- After that, nearby users answer a one-tap "blocked or unblocked?" prompt.
  The status flips when 4 different users report the opposite of it.
- A user who reported too many blocked segments recently must send a photo.
- AI never decides alone: a rejected photo stays "unverified", and a photo the
  agent could not review stays "pending". Neither affects routing.

Everything is in memory here; storage and login come in later steps.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum

from app.config import BLOCK_REPORT_WINDOW, MAX_BLOCK_REPORTS_IN_WINDOW, VOTES_TO_FLIP
from app.routing import Hazard, Hazards, SegmentKey

BLOCKED_HAZARD = Hazard(kind="blocked", severity=1.0, blocked=True)


class SegmentStatus(str, Enum):
    OPEN = "open"
    BLOCKED = "blocked"


class PhotoVerdict(str, Enum):
    """What the photo agent said. The value is the report's `verification` in GET /reports."""

    CONFIRMED = "confirmed"  # agent agrees the photo shows a blocked sidewalk
    REJECTED = "unverified"  # agent does not see a blocked sidewalk
    UNAVAILABLE = "pending"  # agent failed or timed out; the photo is re-sent later


class ReportOutcome(str, Enum):
    STATUS_CHANGED = "status_changed"
    VOTE_RECORDED = "vote_recorded"
    UNVERIFIED = "unverified"
    PENDING = "pending"
    PHOTO_REQUIRED = "photo_required"


PhotoReviewer = Callable[[bytes], PhotoVerdict]


def new_report_id() -> str:
    return f"r_{uuid.uuid4().hex[:12]}"


@dataclass(frozen=True)
class PhotoReport:
    report_id: str
    segment: SegmentKey
    user_id: str
    photo: bytes  # kept only while pending, so the photo can be re-reviewed
    reported_at: datetime
    verdict: PhotoVerdict


def _drop_photo_once_reviewed(report: PhotoReport) -> PhotoReport:
    if report.verdict is PhotoVerdict.UNAVAILABLE:
        return report
    return replace(report, photo=b"")


class SegmentReports:
    """Status of every reported segment, plus the evidence behind it."""

    def __init__(self, review_photo: PhotoReviewer) -> None:
        self._review_photo = review_photo
        self._status: dict[SegmentKey, SegmentStatus] = {}
        # Latest vote per user since the segment's last status change.
        self._votes: dict[SegmentKey, dict[str, SegmentStatus]] = {}
        self._block_reports: dict[str, list[datetime]] = {}
        self._photo_reports: list[PhotoReport] = []

    def status(self, segment: SegmentKey) -> SegmentStatus:
        return self._status.get(segment, SegmentStatus.OPEN)

    def report_blocked_with_photo(
        self,
        segment: SegmentKey,
        user_id: str,
        photo: bytes,
        now: datetime,
        *,
        report_id: str | None = None,
        verdict: PhotoVerdict | None = None,
    ) -> ReportOutcome:
        """Record a photo report. Pass `verdict` when the photo was already
        reviewed (by the API outside its lock, or when replaying storage);
        otherwise the reviewer is called here."""
        self._remember_block_report(user_id, now)
        if verdict is None:
            verdict = self._review_photo(photo)
        report = PhotoReport(report_id or new_report_id(), segment, user_id, photo, now, verdict)
        self._photo_reports.append(_drop_photo_once_reviewed(report))
        return self._apply(report)

    def needs_photo(self, user_id: str, now: datetime) -> bool:
        """True if a blocked vote from this user would get PHOTO_REQUIRED."""
        return self._too_many_block_reports(user_id, now)

    def vote(self, segment: SegmentKey, user_id: str, blocked: bool, now: datetime) -> ReportOutcome:
        if blocked and self.needs_photo(user_id, now):
            return ReportOutcome.PHOTO_REQUIRED
        if blocked:
            self._remember_block_report(user_id, now)

        wanted = SegmentStatus.BLOCKED if blocked else SegmentStatus.OPEN
        votes = self._votes.setdefault(segment, {})
        votes[user_id] = wanted
        opposing = sum(1 for vote in votes.values() if vote is not self.status(segment))
        if opposing >= VOTES_TO_FLIP:
            self._set_status(segment, wanted)
            return ReportOutcome.STATUS_CHANGED
        return ReportOutcome.VOTE_RECORDED

    def pending_photos(self) -> list[PhotoReport]:
        """Photo reports still waiting for the agent (#53), oldest first."""
        return [report for report in self._photo_reports if report.verdict is PhotoVerdict.UNAVAILABLE]

    def resolve_pending(self, report_id: str, verdict: PhotoVerdict) -> ReportOutcome | None:
        """Apply a late verdict to a pending photo. None if it isn't pending anymore."""
        for i, report in enumerate(self._photo_reports):
            if report.report_id == report_id and report.verdict is PhotoVerdict.UNAVAILABLE:
                report = replace(report, verdict=verdict)
                self._photo_reports[i] = _drop_photo_once_reviewed(report)
                return self._apply(report)
        return None

    def retry_pending(self) -> None:
        """Re-send photos the agent could not review earlier."""
        for i, report in enumerate(self._photo_reports):
            if report.verdict is PhotoVerdict.UNAVAILABLE:
                report = replace(report, verdict=self._review_photo(report.photo))
                self._photo_reports[i] = _drop_photo_once_reviewed(report)
                self._apply(report)

    def hazards(self) -> Hazards:
        """Routing input: only confirmed blocked segments."""
        return {
            segment: [BLOCKED_HAZARD]
            for segment, status in self._status.items()
            if status is SegmentStatus.BLOCKED
        }

    def photo_reports(self) -> list[PhotoReport]:
        """Every photo report, oldest first; `verdict` says confirmed, unverified or pending."""
        return list(self._photo_reports)

    def reported_segments(self) -> set[SegmentKey]:
        """Every segment with a status, a current vote or a photo report."""
        segments = set(self._status)
        segments.update(segment for segment, votes in self._votes.items() if votes)
        segments.update(report.segment for report in self._photo_reports)
        return segments

    def _apply(self, report: PhotoReport) -> ReportOutcome:
        """Apply a report's verdict to its segment's status."""
        if report.verdict is PhotoVerdict.UNAVAILABLE:
            return ReportOutcome.PENDING
        if report.verdict is PhotoVerdict.REJECTED:
            return ReportOutcome.UNVERIFIED
        if self.status(report.segment) is SegmentStatus.BLOCKED:
            return ReportOutcome.VOTE_RECORDED
        self._set_status(report.segment, SegmentStatus.BLOCKED)
        return ReportOutcome.STATUS_CHANGED

    def _set_status(self, segment: SegmentKey, status: SegmentStatus) -> None:
        self._status[segment] = status
        self._votes[segment] = {}  # votes before a change don't carry over

    def _too_many_block_reports(self, user_id: str, now: datetime) -> bool:
        recent = [t for t in self._block_reports.get(user_id, []) if now - t < BLOCK_REPORT_WINDOW]
        self._block_reports[user_id] = recent
        return len(recent) >= MAX_BLOCK_REPORTS_IN_WINDOW

    def _remember_block_report(self, user_id: str, now: datetime) -> None:
        self._block_reports.setdefault(user_id, []).append(now)
