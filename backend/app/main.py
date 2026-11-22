"""Lumi API: street routing and community reports around Boston University."""

import logging
import os
import threading
from collections.abc import Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated, Literal

import networkx as nx
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import InvalidToken, TokenVerifier, clerk_verifier_from_env
from app.config import (
    DEMO_MODE_ENV,
    DEMO_PHOTO_USER,
    DEMO_USER_PREFIX,
    GRAPH_PATH,
    MAX_DEMO_VOTERS,
    MAX_PHOTO_BYTES,
    MAX_PENDING_REVIEW_RETRIES,
    MAX_PHOTO_REPORTS_IN_WINDOW,
    MAX_SNAP_DISTANCE_M,
    NEARBY_RADIUS_M,
    PENDING_RETRY_INTERVAL_S,
    PHOTO_REPORT_WINDOW,
    VOTES_TO_FLIP,
    frontend_origins,
)
from app.photo_review import detect_media_type, make_mastra_reviewer
from app.reports import PhotoReviewer, PhotoVerdict, SegmentReports, SegmentStatus, new_report_id
from app.routing import (
    Hazards,
    NoRouteError,
    RouteHazard,
    RouteMode,
    SegmentKey,
    find_route,
    nearest_node,
    segment_key,
)
from app.routing import segment_id as make_segment_id
from app.segments import SegmentIndex
from app.storage import MemoryReportStore, PostgresReportStore, StoredReport, default_store, new_vote_id, replay

logger = logging.getLogger(__name__)

Latitude = Annotated[float, Query(ge=-90, le=90)]
Longitude = Annotated[float, Query(ge=-180, le=180)]


class RouteOut(BaseModel):
    mode: RouteMode
    mode_description: str
    distance_m: float
    coordinates: list[tuple[float, float]]  # (lat, lon)
    snapped_start: tuple[float, float]  # (lat, lon) of the intersection the route starts at
    snapped_end: tuple[float, float]  # (lat, lon) of the intersection the route ends at
    hazards: list[RouteHazard]  # only confirmed reports reach routing; GET /reports lists the rest


class ReportOut(BaseModel):
    report_id: str
    segment_id: str
    outcome: Literal["status_changed", "vote_recorded", "unverified", "pending"]
    segment_status: SegmentStatus


class VoteIn(BaseModel):
    blocked: bool
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class VoteOut(BaseModel):
    outcome: Literal["vote_recorded", "status_changed", "photo_required"]
    segment_status: SegmentStatus


class DemoVotesIn(BaseModel):
    blocked: bool
    voters: int = Field(default=VOTES_TO_FLIP, ge=1, le=MAX_DEMO_VOTERS)


class DemoVotesOut(BaseModel):
    votes_cast: int
    outcome: Literal["vote_recorded", "status_changed", "photo_required"]  # from the last voter
    segment_status: SegmentStatus


class DemoResetOut(BaseModel):
    removed: int


class DemoNearestOut(BaseModel):
    segment_id: str
    distance_m: float


class NearbySegmentOut(BaseModel):
    segment_id: str
    status: SegmentStatus
    coordinates: list[tuple[float, float]]  # (lat, lon) along the segment


class ReportListItem(BaseModel):
    report_id: str
    segment_id: str
    location: tuple[float, float]  # (lat, lon) segment midpoint, same as /route hazards
    verification: PhotoVerdict  # "confirmed", "unverified" or "pending"
    reported_at: str  # ISO 8601 UTC, e.g. "2026-11-21T18:04:00Z"
    simulated: bool


def load_street_graph() -> nx.DiGraph:
    import osmnx as ox  # heavy import; only needed for the real graph

    if not GRAPH_PATH.exists():
        raise RuntimeError(f"Street graph missing at {GRAPH_PATH}. Run: uv run python scripts/build_graph.py")
    return ox.convert.to_digraph(ox.load_graphml(GRAPH_PATH), weight="length")



SIGN_IN_REQUIRED = "Sign in to report or answer questions about sidewalks."
SIGN_IN_INVALID = "Your sign-in has expired or isn't valid. Please sign in again."


def require_user(request: Request, authorization: Annotated[str | None, Header()] = None) -> str:
    """The signed-in Clerk user's ID, from `Authorization: Bearer <session token>` (#14)."""
    verify: TokenVerifier | None = request.app.state.verify_token
    if verify is None:
        raise HTTPException(status_code=503, detail="Sign-in isn't set up on the server yet. Please try again later.")
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail=SIGN_IN_REQUIRED, headers={"WWW-Authenticate": "Bearer"})
    try:
        return verify(token.strip())
    except InvalidToken as error:
        logger.info("Rejected session token: %s", error)
        raise HTTPException(status_code=401, detail=SIGN_IN_INVALID, headers={"WWW-Authenticate": "Bearer"}) from None


UserId = Annotated[str, Depends(require_user)]


def create_app(
    graph: nx.DiGraph | None = None,
    hazards: Hazards | None = None,
    review_photo: PhotoReviewer | None = None,
    store: PostgresReportStore | MemoryReportStore | None = None,
    verify_token: TokenVerifier | None = None,
    demo_mode: bool | None = None,
) -> FastAPI:
    """`hazards` are fixed extra hazards (tests use them); confirmed reports are added on top.

    `store` defaults to Tiger Data if PGHOST is set, else memory (see app/storage.py).
    `verify_token` defaults to Clerk from CLERK_ISSUER / CLERK_JWKS_URL (see app/auth.py).
    `demo_mode` defaults to LUMI_DEMO_MODE=1; it adds the /demo endpoints (#38).
    """
    if verify_token is None:
        verify_token = clerk_verifier_from_env(frontend_origins())
    if verify_token is None:
        logger.warning("CLERK_ISSUER / CLERK_JWKS_URL not set: reports and votes will answer 503.")
    if demo_mode is None:
        demo_mode = os.environ.get(DEMO_MODE_ENV) == "1"
    # The Mastra photo agent (LUMI_MASTRA_URL). If it's down, reports stay pending.
    reviewer = review_photo if review_photo is not None else make_mastra_reviewer()
    static_hazards = hazards if hazards is not None else {}
    # Set at startup by `lifespan`; the endpoints below read them.
    street_graph: nx.DiGraph
    segments: SegmentIndex
    reports: SegmentReports
    report_store: PostgresReportStore | MemoryReportStore  # every write goes here first, then to `reports`
    simulated_ids: set[str] = set()  # photo reports created by /demo endpoints, shown as "Simulated"
    # SegmentReports isn't thread-safe and FastAPI runs sync endpoints in a
    # thread pool, so every read and write of `reports` holds this lock. Writes
    # also hold it while saving to the store, so stored order = applied order.
    lock = threading.Lock()
    photo_reviews: dict[str, list[datetime]] = {}  # user -> when their photos went to the reviewer (#82)

    def reserve_photo_review(user_id: str) -> bool:
        """Count one review for this user, or return False if they're over the limit."""
        now = datetime.now(UTC)
        with lock:
            recent = [t for t in photo_reviews.get(user_id, []) if now - t < PHOTO_REPORT_WINDOW]
            if len(recent) >= MAX_PHOTO_REPORTS_IN_WINDOW:
                photo_reviews[user_id] = recent
                return False
            photo_reviews[user_id] = [*recent, now]
            return True

    def rebuild_from_store() -> int:
        """Replace in-memory status with a replay of the stored rows (startup and demo reset)."""
        nonlocal reports, simulated_ids
        rows = report_store.all()
        reports = SegmentReports(review_photo=reviewer)
        simulated_ids = {row.report_id for row in rows if row.simulated}
        return replay(rows, reports, segments)  # stored statuses; never calls the reviewer

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal street_graph, segments, report_store
        street_graph = graph if graph is not None else load_street_graph()
        segments = SegmentIndex(street_graph)
        report_store = store if store is not None else default_store()
        replayed = rebuild_from_store()
        logger.info("Rebuilt segment status from %d stored reports", replayed)
        stop_retrying = threading.Event()
        retrier = threading.Thread(target=retry_until_stopped, args=(stop_retrying,), daemon=True)
        retrier.start()
        try:
            yield
        finally:
            stop_retrying.set()
            retrier.join()  # it stops between photos, so at most one reviewer call (20 s) to finish
            if store is None:  # we opened it, so we close it
                report_store.close()

    retries: dict[str, int] = {}  # report id -> reviewer calls made by retries this run

    def retry_pending_photos(stop: threading.Event | None = None) -> int:
        """Re-send pending photos to the agent and apply any verdict (#53). Returns how many resolved.

        The agent is called outside the lock, like in POST /reports, so a slow
        agent never blocks routing. Each verdict is saved before it's applied.
        Each photo is retried at most MAX_PENDING_REVIEW_RETRIES times per run (each
        is a paid call), and `stop` is checked between photos so shutdown never waits
        on a long backlog.
        """
        with lock:
            waiting = reports.pending_photos()
        resolved = 0
        for photo_report in waiting:
            if stop is not None and stop.is_set():
                break
            attempts = retries.get(photo_report.report_id, 0)
            if attempts >= MAX_PENDING_REVIEW_RETRIES:
                continue
            retries[photo_report.report_id] = attempts + 1
            verdict = _review(reviewer, photo_report.photo)
            if verdict is PhotoVerdict.UNAVAILABLE:
                continue
            with lock:
                try:
                    report_store.update_status(photo_report.report_id, verdict, datetime.now(UTC))
                except Exception:
                    logger.exception("Couldn't save the new verdict for %s; will retry", photo_report.report_id)
                    continue
                if reports.resolve_pending(photo_report.report_id, verdict) is not None:
                    resolved += 1
        if resolved:
            logger.info("Resolved %d pending photo reports", resolved)
        return resolved

    def retry_until_stopped(stop: threading.Event) -> None:
        while not stop.wait(PENDING_RETRY_INTERVAL_S):
            try:
                retry_pending_photos(stop)
            except Exception:  # keep retrying on the next tick
                logger.exception("Pending photo retry failed")

    def save(row: StoredReport) -> None:
        """Store first: if saving fails, the report isn't applied and the user can retry."""
        try:
            report_store.add(row)
        except Exception as error:
            logger.exception("Couldn't save report %s", row.report_id)
            raise HTTPException(
                status_code=503, detail="Lumi couldn't save your report right now. Please try again."
            ) from error

    app = FastAPI(title="Lumi API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=frontend_origins(),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization"],
    )
    app.state.verify_token = verify_token
    app.state.retry_pending_photos = retry_pending_photos  # tests and ops can trigger a retry

    @app.exception_handler(RequestValidationError)
    async def readable_validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        """The API contract promises `detail` is a string, so join FastAPI's error list into one."""
        return JSONResponse(status_code=422, content={"detail": validation_message(error.errors())})

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/route", response_model=RouteOut)
    def route(
        start_lat: Latitude,
        start_lon: Longitude,
        end_lat: Latitude,
        end_lon: Longitude,
        mode: RouteMode = RouteMode.SAFER,
    ) -> RouteOut:
        start = _snap(street_graph, start_lat, start_lon, "Start")
        end = _snap(street_graph, end_lat, end_lon, "Destination")
        if start == end:
            raise HTTPException(
                status_code=422,
                detail="Start and destination are too close to route between. Pick points farther apart.",
            )
        with lock:
            route_hazards = _merge_hazards(static_hazards, reports.hazards())
        try:
            result = find_route(street_graph, start, end, mode, route_hazards)
        except NoRouteError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return RouteOut(
            mode=mode,
            mode_description=mode.description,
            distance_m=round(result.distance_m, 1),
            coordinates=result.coordinates,
            snapped_start=_lat_lon(street_graph, start),
            snapped_end=_lat_lon(street_graph, end),
            hazards=result.hazards,
        )

    # Sync (not async) so FastAPI runs it in a worker thread: the photo
    # reviewer can take seconds and must not block the event loop.
    @app.post("/reports", status_code=201, response_model=ReportOut)
    def create_report(
        user_id: UserId,
        lat: Annotated[float, Form(ge=-90, le=90)],
        lon: Annotated[float, Form(ge=-180, le=180)],
        photo: Annotated[UploadFile, File()],
    ) -> ReportOut:
        data = photo.file.read(MAX_PHOTO_BYTES + 1)
        if len(data) > MAX_PHOTO_BYTES:
            raise HTTPException(status_code=413, detail="The photo is larger than 5 MB. Send a smaller one.")
        if detect_media_type(data) is None:  # by content; filename and Content-Type are easy to get wrong
            raise HTTPException(status_code=415, detail="The photo must be a JPEG, PNG or WebP image.")
        sid, distance_m = segments.nearest(lat, lon)
        if distance_m > MAX_SNAP_DISTANCE_M:
            raise HTTPException(
                status_code=422,
                detail=f"This spot is outside Lumi's coverage area ({distance_m:.0f} m from the nearest mapped sidewalk).",
            )

        if not reserve_photo_review(user_id):
            raise HTTPException(
                status_code=429,
                detail=f"You've sent {MAX_PHOTO_REPORTS_IN_WINDOW} photo reports in the last hour. Try again later.",
            )
        verdict = _review(reviewer, data)  # outside the lock: it may be slow
        report_id = new_report_id()
        segment = _key(segments, sid)
        with lock:
            # Timestamped inside the lock, so time order matches the order the rules saw.
            reported_at = datetime.now(UTC)
            save(StoredReport(report_id, sid, user_id, lat, lon, True, reported_at, status=verdict, photo=data))
            outcome = reports.report_blocked_with_photo(
                segment, user_id, data, reported_at, report_id=report_id, verdict=verdict
            )
            status = reports.status(segment)
        return ReportOut(report_id=report_id, segment_id=sid, outcome=outcome.value, segment_status=status)

    @app.post("/segments/{segment_id}/votes", response_model=VoteOut)
    def vote(segment_id: str, body: VoteIn, user_id: UserId) -> VoteOut:
        if segment_id not in segments:
            raise HTTPException(status_code=404, detail=f"No sidewalk segment with id {segment_id}.")
        distance_m = segments.distance_m(segment_id, body.lat, body.lon)
        if distance_m > NEARBY_RADIUS_M:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"You need to be within {NEARBY_RADIUS_M} m of this sidewalk to vote on it "
                    f"(you're {distance_m:.0f} m away)."
                ),
            )
        segment = _key(segments, segment_id)
        with lock:
            now = datetime.now(UTC)
            if body.blocked and reports.needs_photo(user_id, now):
                # Refused, so nothing to store: replay would refuse it again anyway.
                return VoteOut(outcome="photo_required", segment_status=reports.status(segment))
            save(StoredReport(new_vote_id(), segment_id, user_id, body.lat, body.lon, body.blocked, now))
            outcome = reports.vote(segment, user_id, body.blocked, now)
            status = reports.status(segment)
        return VoteOut(outcome=outcome.value, segment_status=status)

    @app.get("/segments/nearby", response_model=list[NearbySegmentOut])
    def nearby_segments(lat: Latitude, lon: Longitude) -> list[NearbySegmentOut]:
        close = segments.within(lat, lon, NEARBY_RADIUS_M)
        with lock:
            reported = {_sid(key): reports.status(key) for key in reports.reported_segments()}
        found = sorted((distance, sid) for sid, distance in close.items() if sid in reported)
        return [
            NearbySegmentOut(segment_id=sid, status=reported[sid], coordinates=segments.coordinates(sid))
            for _, sid in found
        ]

    @app.get("/reports", response_model=list[ReportListItem])
    def list_reports() -> list[ReportListItem]:
        with lock:
            # A confirmed photo stops being shown once votes reopen its segment:
            # drawing it would contradict the segment's current status.
            listed = [
                r
                for r in reports.photo_reports()
                if r.verdict is not PhotoVerdict.CONFIRMED or reports.status(r.segment) is SegmentStatus.BLOCKED
            ]
        listed.sort(key=lambda r: r.reported_at, reverse=True)  # newest first
        return [
            ReportListItem(
                report_id=r.report_id,
                segment_id=sid,
                location=segments.midpoint(sid),
                verification=r.verdict,
                reported_at=_iso_utc(r.reported_at),
                simulated=r.report_id in simulated_ids,
            )
            for r in listed
            if (sid := _sid(r.segment)) in segments  # a report off this graph can't be placed on the map
        ]

    if not demo_mode:
        return app  # the /demo endpoints below don't exist, so they're 404

    # --- Demo mode (#38): simulated users "sim-1" ... "sim-N". They skip login
    # and the nearby check, but the normal report rules still apply. Every row
    # they create is stored with simulated=True and shown as "Simulated".

    def demo_segment(segment_id: str) -> SegmentKey:
        if segment_id not in segments:
            raise HTTPException(status_code=404, detail=f"No sidewalk segment with id {segment_id}.")
        return _key(segments, segment_id)

    @app.get("/demo/status")
    def demo_status() -> dict:
        """Lets the frontend show its Demo panel only when demo mode is on (404 otherwise)."""
        return {"demo_mode": True}

    @app.get("/demo/segments/nearest", response_model=DemoNearestOut)
    def demo_nearest(lat: Latitude, lon: Longitude) -> DemoNearestOut:
        """The sidewalk segment closest to a point, e.g. halfway along a route the demo will block."""
        sid, distance_m = segments.nearest(lat, lon)
        if distance_m > MAX_SNAP_DISTANCE_M:
            raise HTTPException(
                status_code=422,
                detail=f"This spot is outside Lumi's coverage area ({distance_m:.0f} m from the nearest mapped sidewalk).",
            )
        return DemoNearestOut(segment_id=sid, distance_m=round(distance_m, 1))

    @app.post("/demo/segments/{segment_id}/block", response_model=ReportOut)
    def demo_block(segment_id: str) -> ReportOut:
        """A simulated photo report the agent "confirmed", without calling the agent."""
        segment = demo_segment(segment_id)
        lat, lon = segments.midpoint(segment_id)
        report_id = new_report_id()
        with lock:
            now = datetime.now(UTC)
            save(
                StoredReport(
                    report_id, segment_id, DEMO_PHOTO_USER, lat, lon, True, now,
                    status=PhotoVerdict.CONFIRMED, photo=b"", simulated=True,
                )
            )
            simulated_ids.add(report_id)
            outcome = reports.report_blocked_with_photo(
                segment, DEMO_PHOTO_USER, b"", now, report_id=report_id, verdict=PhotoVerdict.CONFIRMED
            )
            status = reports.status(segment)
        return ReportOut(report_id=report_id, segment_id=segment_id, outcome=outcome.value, segment_status=status)

    @app.post("/demo/segments/{segment_id}/votes", response_model=DemoVotesOut)
    def demo_votes(segment_id: str, body: DemoVotesIn) -> DemoVotesOut:
        segment = demo_segment(segment_id)
        lat, lon = segments.midpoint(segment_id)
        outcome = None
        with lock:
            for n in range(1, body.voters + 1):
                user = f"{DEMO_USER_PREFIX}{n}"
                now = datetime.now(UTC)
                if body.blocked and reports.needs_photo(user, now):
                    outcome = "photo_required"
                    continue
                save(StoredReport(new_vote_id(), segment_id, user, lat, lon, body.blocked, now, simulated=True))
                outcome = reports.vote(segment, user, body.blocked, now).value
            status = reports.status(segment)
        return DemoVotesOut(votes_cast=body.voters, outcome=outcome, segment_status=status)

    @app.post("/demo/reset", response_model=DemoResetOut)
    def demo_reset() -> DemoResetOut:
        """Delete simulated rows only, then rebuild every segment's status from the real ones."""
        with lock:
            removed = report_store.delete_simulated()
            rebuild_from_store()
        logger.info("Demo reset: removed %d simulated rows", removed)
        return DemoResetOut(removed=removed)

    return app


_REQUEST_PARTS = {"query", "body", "path", "header", "form"}


def validation_message(errors: Sequence[dict]) -> str:
    """e.g. "start_lat: Input should be less than or equal to 90; start_lon: Field required"."""
    parts = []
    for error in errors:
        field = ".".join(str(part) for part in error.get("loc", ()) if part not in _REQUEST_PARTS)
        message = error.get("msg", "Invalid value")
        parts.append(f"{field}: {message}" if field else message)
    return "; ".join(parts) or "Invalid request."


def _review(review_photo: PhotoReviewer, photo: bytes) -> PhotoVerdict:
    """A reviewer that crashes counts as unavailable: the report waits as pending."""
    try:
        return review_photo(photo)
    except Exception:
        logger.exception("Photo reviewer failed; keeping the report pending")
        return PhotoVerdict.UNAVAILABLE


def _key(segments: SegmentIndex, sid: str) -> SegmentKey:
    return segment_key(*segments.endpoints(sid))


def _sid(key: SegmentKey) -> str:
    return make_segment_id(min(key), max(key))


def _merge_hazards(static: Hazards, reported: Hazards) -> Hazards:
    merged = {segment: list(found) for segment, found in static.items()}
    for segment, found in reported.items():
        merged.setdefault(segment, []).extend(found)
    return merged


def _iso_utc(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _snap(graph: nx.DiGraph, lat: float, lon: float, label: str):
    node, distance_m = nearest_node(graph, lat, lon)
    if distance_m > MAX_SNAP_DISTANCE_M:
        raise HTTPException(
            status_code=422,
            detail=f"{label} is outside Lumi's coverage area ({distance_m:.0f} m from the nearest mapped intersection).",
        )
    return node


def _lat_lon(graph: nx.DiGraph, node) -> tuple[float, float]:
    return (graph.nodes[node]["y"], graph.nodes[node]["x"])


app = create_app()
