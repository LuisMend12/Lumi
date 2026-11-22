"""Report storage: one row per photo report or counted vote, replayed on startup.

The rows are the source of truth. On startup the API rebuilds `SegmentReports`
by replaying them oldest first with each photo's stored status, so the photo
reviewer is never called during replay. Every write goes to the store first and
then to memory.

- `PostgresReportStore`: Tiger Data (TimescaleDB), used when PGHOST is set. It
  connects with the standard libpq variables (PGHOST, PGPORT, PGDATABASE,
  PGUSER, PGPASSWORD, PGSSLMODE) and creates its table on startup.
- `MemoryReportStore`: for tests and for running without a database.
"""

import logging
import os
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime

import psycopg

from app.reports import PhotoVerdict, SegmentReports
from app.routing import segment_key
from app.segments import SegmentIndex

logger = logging.getLogger(__name__)

# Safe to run on every startup.
SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS reports (
        report_id   text             NOT NULL,  -- "r_..." for photo reports, "v_..." for votes
        segment_id  text             NOT NULL,  -- "<u>-<v>", smaller OSM node id first
        user_id     text             NOT NULL,  -- Clerk user id (token "sub"); older rows: X-User-Id
        lat         double precision NOT NULL,  -- where the user was
        lon         double precision NOT NULL,
        blocked     boolean          NOT NULL,  -- always true for photo reports
        status      text,                       -- photo reports: confirmed, unverified or pending. NULL = vote
        photo       bytea,                      -- photo reports only
        simulated   boolean          NOT NULL DEFAULT false,  -- demo data from /demo endpoints (#38)
        reported_at timestamptz      NOT NULL
    )
    """,
    "SELECT create_hypertable('reports', 'reported_at', if_not_exists => TRUE)",
    # When a pending photo got its verdict (#53). NULL = decided when reported.
    "ALTER TABLE reports ADD COLUMN IF NOT EXISTS decided_at timestamptz",
]

# Lets a retried insert skip a row that already landed (#91). On a hypertable a
# unique index must include the time column, so it's (report_id, reported_at).
UNIQUE_INDEX = "CREATE UNIQUE INDEX IF NOT EXISTS reports_report_id_idx ON reports (report_id, reported_at)"


def new_vote_id() -> str:
    return f"v_{uuid.uuid4().hex[:12]}"


@dataclass(frozen=True)
class StoredReport:
    """One photo report (`status` set) or one counted vote (`status` is None)."""

    report_id: str
    segment_id: str
    user_id: str
    lat: float
    lon: float
    blocked: bool
    reported_at: datetime
    status: PhotoVerdict | None = None
    photo: bytes | None = None
    simulated: bool = False  # created by a demo endpoint, not a real person
    decided_at: datetime | None = None  # a late verdict's time; None = decided when reported

    @property
    def effective_at(self) -> datetime:
        """When this row took effect: replay applies rows in this order."""
        return self.decided_at or self.reported_at


class MemoryReportStore:
    """Keeps rows in a list: they survive an app restart only within one process (tests)."""

    def __init__(self) -> None:
        self._rows: list[StoredReport] = []

    def add(self, row: StoredReport) -> None:
        if any((r.report_id, r.reported_at) == (row.report_id, row.reported_at) for r in self._rows):
            return  # same as Postgres: a repeated insert is ignored (#91)
        self._rows.append(row)

    def all(self) -> list[StoredReport]:
        return sorted(self._rows, key=lambda row: (row.reported_at, row.report_id))

    def update_status(self, report_id: str, status: PhotoVerdict, decided_at: datetime) -> None:
        """A pending photo got its verdict (#53): store it, when, and drop the photo bytes."""
        self._rows = [
            replace(row, status=status, photo=None, decided_at=decided_at) if row.report_id == report_id else row
            for row in self._rows
        ]

    def delete_simulated(self) -> int:
        kept = [row for row in self._rows if not row.simulated]
        removed = len(self._rows) - len(kept)
        self._rows = kept
        return removed

    def close(self) -> None:
        pass


class PostgresReportStore:
    """Tiger Data store. `conninfo=""` reads the PG* environment variables."""

    def __init__(self, conninfo: str = "") -> None:
        self._conninfo = conninfo
        self._conn = psycopg.connect(conninfo, autocommit=True)
        for statement in SCHEMA:
            self._conn.execute(statement)
        try:
            self._conn.execute(UNIQUE_INDEX)
        except psycopg.Error as error:
            # Existing duplicate rows block the index. Keep running: inserts still
            # work, they just can't skip duplicates until the old rows are cleaned up.
            logger.warning("Couldn't create the unique report index (%s); duplicate rows aren't prevented", error)

    def add(self, row: StoredReport) -> None:
        try:
            self._insert(row)
        except psycopg.OperationalError:
            # The connection dropped since the last call: reconnect once and retry (#61).
            # The first insert may have committed before the connection dropped;
            # ON CONFLICT DO NOTHING in _insert keeps the retry from adding it twice (#91).
            logger.warning("Insert failed on a dropped connection; reconnecting once")
            self._reconnect()
            self._insert(row)

    def _insert(self, row: StoredReport) -> None:
        self._connection().execute(
            "INSERT INTO reports"
            " (report_id, segment_id, user_id, lat, lon, blocked, status, photo, simulated, reported_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT DO NOTHING",
            (
                row.report_id,
                row.segment_id,
                row.user_id,
                row.lat,
                row.lon,
                row.blocked,
                row.status.value if row.status else None,
                row.photo,
                row.simulated,
                row.reported_at,
            ),
        )

    def all(self) -> list[StoredReport]:
        """Every row, oldest first. Only pending photos come back with their bytes:
        nothing else needs them, and loading every photo would slow startup."""
        rows = self._connection().execute(
            "SELECT report_id, segment_id, user_id, lat, lon, blocked, reported_at, status,"
            " CASE WHEN status = 'pending' THEN photo END, simulated, decided_at"
            " FROM reports ORDER BY reported_at, report_id"
        ).fetchall()
        return [
            StoredReport(
                *columns,
                reported_at=reported_at.astimezone(UTC),
                status=PhotoVerdict(status) if status else None,
                photo=bytes(photo) if photo is not None else None,
                simulated=simulated,
                decided_at=decided_at.astimezone(UTC) if decided_at is not None else None,
            )
            for *columns, reported_at, status, photo, simulated, decided_at in rows
        ]

    def update_status(self, report_id: str, status: PhotoVerdict, decided_at: datetime) -> None:
        """A pending photo got its verdict (#53): store it, when, and drop the photo bytes."""
        self._connection().execute(
            "UPDATE reports SET status = %s, photo = NULL, decided_at = %s WHERE report_id = %s",
            (status.value, decided_at, report_id),
        )

    def delete_simulated(self) -> int:
        """Remove demo rows only. Returns how many were deleted."""
        return self._connection().execute("DELETE FROM reports WHERE simulated").rowcount

    def close(self) -> None:
        self._conn.close()

    def _connection(self) -> psycopg.Connection:
        """The open connection, reconnecting once if the last one dropped."""
        if self._conn.closed or self._conn.broken:
            logger.warning("Database connection lost; reconnecting")
            self._reconnect()
        return self._conn

    def _reconnect(self) -> None:
        """Close the dropped connection (ignoring errors) and open a new one."""
        try:
            self._conn.close()
        except psycopg.Error:
            pass
        self._conn = psycopg.connect(self._conninfo, autocommit=True)


def default_store() -> PostgresReportStore | MemoryReportStore:
    """Postgres if PGHOST is set, otherwise memory (reports are lost on restart)."""
    if os.environ.get("PGHOST"):
        return PostgresReportStore()
    logger.warning("PGHOST is not set: reports are kept in memory and lost when the server stops.")
    return MemoryReportStore()


def replay(rows: list[StoredReport], book: SegmentReports, segments: SegmentIndex) -> int:
    """Apply stored rows to `book` in the order they took effect, with each photo's stored status.

    A photo whose verdict came late (#53) is applied when it was decided, not when it
    was reported, so votes cast in between replay before it, exactly as they happened.
    The reviewer is never called here. Returns how many rows were applied.
    """
    applied = 0
    # On a tie (clocks tick ~15 ms on Windows), a late verdict goes last: it was decided
    # after every row already stored at that instant.
    for row in sorted(rows, key=lambda row: (row.effective_at, row.decided_at is not None, row.report_id)):
        if row.segment_id not in segments:
            logger.warning("Skipping stored report %s: segment %s isn't in the street graph", row.report_id, row.segment_id)
            continue
        segment = segment_key(*segments.endpoints(row.segment_id))
        if row.status is None:
            book.vote(segment, row.user_id, row.blocked, row.reported_at)
        else:
            book.report_blocked_with_photo(
                segment, row.user_id, row.photo or b"", row.reported_at, report_id=row.report_id, verdict=row.status
            )
        applied += 1
    return applied
