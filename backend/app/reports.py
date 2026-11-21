"""Community reports that decide whether a sidewalk segment is blocked.

Rules (team decisions):
- A "blocked" report with a photo counts only if the photo agent confirms it;
  a confirmed photo report blocks the segment right away.
- After that, nearby users answer a one-tap "blocked or unblocked?" prompt.
  The status flips when 4 different users report the opposite of it.
- A user who reported too many blocked segments recently must send a photo.
- AI never decides alone: a rejected photo stays "unverified", and a photo the
  agent could not review stays "pending". Neither affects routing.

Everything is in memory for now; storage and login come in later steps.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.config import BLOCK_REPORT_WINDOW, MAX_BLOCK_REPORTS_IN_WINDOW, VOTES_TO_FLIP
from app.routing import Hazard, Hazards, SegmentKey

BLOCKED_HAZARD = Hazard(kind="blocked", severity=1.0, blocked=True)


class SegmentStatus(str, Enum):
    OPEN = "open"
    BLOCKED = "blocked"


class PhotoVerdict(str, Enum):
    CONFIRMED = "confirmed"  # agent agrees the photo shows a blocked sidewalk
    REJECTED = "rejected"  # agent does not see a blocked sidewalk
    UNAVAILABLE = "unavailable"  # agent failed or timed out


class ReportOutcome(str, Enum):
    STATUS_CHANGED = "status_changed"
    VOTE_RECORDED = "vote_recorded"
    UNVERIFIED = "unverified"
    PENDING = "pending"
    PHOTO_REQUIRED = "photo_required"


PhotoReviewer = Callable[[bytes], PhotoVerdict]


@dataclass(frozen=True)
class PhotoReport:
    segment: SegmentKey
    user_id: str
    photo: bytes
    reported_at: datetime


class SegmentReports:
    """Status of every reported segment, plus the evidence behind it."""

    def __init__(self, review_photo: PhotoReviewer) -> None:
        self._review_photo = review_photo
        self._status: dict[SegmentKey, SegmentStatus] = {}
        # Latest vote per user since the segment's last status change.
        self._votes: dict[SegmentKey, dict[str, SegmentStatus]] = {}
        self._block_reports: dict[str, list[datetime]] = {}
        self._unverified: list[PhotoReport] = []
        self._pending: list[PhotoReport] = []

    def status(self, segment: SegmentKey) -> SegmentStatus:
        return self._status.get(segment, SegmentStatus.OPEN)

    def report_blocked_with_photo(
        self, segment: SegmentKey, user_id: str, photo: bytes, now: datetime
    ) -> ReportOutcome:
        self._remember_block_report(user_id, now)
        return self._apply_review(PhotoReport(segment, user_id, photo, now))

    def vote(self, segment: SegmentKey, user_id: str, blocked: bool, now: datetime) -> ReportOutcome:
        if blocked and self._too_many_block_reports(user_id, now):
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

    def retry_pending(self) -> None:
        """Re-send photos the agent could not review earlier."""
        waiting, self._pending = self._pending, []
        for report in waiting:
            self._apply_review(report)

    def hazards(self) -> Hazards:
        """Routing input: only confirmed blocked segments."""
        return {
            segment: [BLOCKED_HAZARD]
            for segment, status in self._status.items()
            if status is SegmentStatus.BLOCKED
        }

    def unverified_reports(self) -> list[PhotoReport]:
        return list(self._unverified)

    def pending_reports(self) -> list[PhotoReport]:
        return list(self._pending)

    def _apply_review(self, report: PhotoReport) -> ReportOutcome:
        verdict = self._review_photo(report.photo)
        if verdict is PhotoVerdict.REJECTED:
            self._unverified.append(report)
            return ReportOutcome.UNVERIFIED
        if verdict is PhotoVerdict.UNAVAILABLE:
            self._pending.append(report)
            return ReportOutcome.PENDING
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
