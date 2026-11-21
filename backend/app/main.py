"""Lumi API: street routing and community reports around Boston University."""

import logging
import threading
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Literal

import networkx as nx
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import GRAPH_PATH, MAX_PHOTO_BYTES, MAX_SNAP_DISTANCE_M, NEARBY_RADIUS_M, frontend_origins
from app.reports import (
    PhotoReport,
    PhotoReviewer,
    PhotoVerdict,
    SegmentReports,
    SegmentStatus,
    new_report_id,
)
from app.routing import Hazards, NoRouteError, RouteMode, SegmentKey, find_route, nearest_node, segment_key
from app.routing import segment_id as make_segment_id
from app.segments import SegmentIndex

logger = logging.getLogger(__name__)

Latitude = Annotated[float, Query(ge=-90, le=90)]
Longitude = Annotated[float, Query(ge=-180, le=180)]
Verification = Literal["confirmed", "unverified", "pending"]


class HazardOut(BaseModel):
    segment_id: str  # "<u>-<v>", smaller OSM node id first
    location: tuple[float, float]  # (lat, lon) segment midpoint, where the warning goes on the map
    kind: str
    severity: float
    blocked: bool
    # Only confirmed reports reach routing; unverified and pending ones are listed by GET /reports.
    verification: Verification


class RouteOut(BaseModel):
    mode: RouteMode
    mode_description: str
    distance_m: float
    coordinates: list[tuple[float, float]]  # (lat, lon)
    snapped_start: tuple[float, float]  # (lat, lon) of the intersection the route starts at
    snapped_end: tuple[float, float]  # (lat, lon) of the intersection the route ends at
    hazards: list[HazardOut]


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


class NearbySegmentOut(BaseModel):
    segment_id: str
    status: SegmentStatus
    coordinates: list[tuple[float, float]]  # (lat, lon) along the segment


class ReportListItem(BaseModel):
    report_id: str
    segment_id: str
    location: tuple[float, float]  # (lat, lon) segment midpoint, same as /route hazards
    verification: Verification
    reported_at: str  # ISO 8601 UTC, e.g. "2026-11-21T18:04:00Z"
    simulated: bool


@dataclass
class _State:
    """Everything the endpoints share, built once at startup."""

    graph: nx.DiGraph
    segments: SegmentIndex
    static_hazards: Hazards  # passed to create_app; kept so tests can set hazards directly
    reports: SegmentReports
    review_photo: PhotoReviewer
    # SegmentReports isn't thread-safe and FastAPI runs sync endpoints in a
    # thread pool, so every read and write of `reports` holds this lock.
    lock: threading.Lock


def load_street_graph() -> nx.DiGraph:
    import osmnx as ox  # heavy import; only needed for the real graph

    if not GRAPH_PATH.exists():
        raise RuntimeError(f"Street graph missing at {GRAPH_PATH}. Run: uv run python scripts/build_graph.py")
    return ox.convert.to_digraph(ox.load_graphml(GRAPH_PATH), weight="length")


def unconfigured_reviewer() -> PhotoReviewer:
    """Stand-in until the real photo agent is wired in: every photo stays pending."""
    warned = False

    def review(photo: bytes) -> PhotoVerdict:
        nonlocal warned
        if not warned:
            logger.warning("No photo reviewer configured: photo reports stay pending and don't affect routing.")
            warned = True
        return PhotoVerdict.UNAVAILABLE

    return review


def require_user(x_user_id: Annotated[str | None, Header()] = None) -> str:
    """Temporary identity until login exists: any stable string the client sends."""
    user_id = (x_user_id or "").strip()
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Missing X-User-Id header. Send a stable id for this device with every report or vote.",
        )
    return user_id


UserId = Annotated[str, Depends(require_user)]


def create_app(
    graph: nx.DiGraph | None = None,
    hazards: Hazards | None = None,
    review_photo: PhotoReviewer | None = None,
) -> FastAPI:
    reviewer = review_photo if review_photo is not None else unconfigured_reviewer()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        street_graph = graph if graph is not None else load_street_graph()
        app.state.lumi = _State(
            graph=street_graph,
            segments=SegmentIndex(street_graph),
            static_hazards=hazards if hazards is not None else {},
            reports=SegmentReports(review_photo=reviewer),
            review_photo=reviewer,
            lock=threading.Lock(),
        )
        yield

    app = FastAPI(title="Lumi API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=frontend_origins(),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-User-Id"],
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/route", response_model=RouteOut)
    def route(
        request: Request,
        start_lat: Latitude,
        start_lon: Longitude,
        end_lat: Latitude,
        end_lon: Longitude,
        mode: RouteMode = RouteMode.SAFER,
    ) -> RouteOut:
        state = _state(request)
        street_graph = state.graph
        start = _snap(street_graph, start_lat, start_lon, "Start")
        end = _snap(street_graph, end_lat, end_lon, "Destination")
        if start == end:
            raise HTTPException(
                status_code=422,
                detail="Start and destination are too close to route between. Pick points farther apart.",
            )
        with state.lock:
            route_hazards = _merge_hazards(state.static_hazards, state.reports.hazards())
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
            hazards=[
                HazardOut(
                    segment_id=rh.segment_id,
                    location=rh.location,
                    kind=rh.hazard.kind,
                    severity=rh.hazard.severity,
                    blocked=rh.hazard.blocked,
                    verification="confirmed",
                )
                for rh in result.hazards
            ],
        )

    # Sync (not async) so FastAPI runs it in a worker thread: the photo
    # reviewer can take seconds and must not block the event loop.
    @app.post("/reports", status_code=201, response_model=ReportOut)
    def create_report(
        request: Request,
        user_id: UserId,
        lat: Annotated[float, Form(ge=-90, le=90)],
        lon: Annotated[float, Form(ge=-180, le=180)],
        photo: Annotated[UploadFile, File()],
    ) -> ReportOut:
        state = _state(request)
        reported_at = datetime.now(UTC)
        data = photo.file.read(MAX_PHOTO_BYTES + 1)
        if len(data) > MAX_PHOTO_BYTES:
            raise HTTPException(status_code=413, detail="The photo is larger than 5 MB. Send a smaller one.")
        if image_type(data) is None:
            raise HTTPException(status_code=415, detail="The photo must be a JPEG, PNG or WebP image.")
        sid, distance_m = state.segments.nearest(lat, lon)
        if distance_m > MAX_SNAP_DISTANCE_M:
            raise HTTPException(
                status_code=422,
                detail=f"This spot is outside Lumi's coverage area ({distance_m:.0f} m from the nearest mapped sidewalk).",
            )

        verdict = _review(state.review_photo, data)  # outside the lock: it may be slow
        report_id = new_report_id()
        segment = _key(state, sid)
        with state.lock:
            outcome = state.reports.report_blocked_with_photo(
                segment, user_id, data, reported_at, report_id=report_id, location=(lat, lon), verdict=verdict
            )
            status = state.reports.status(segment)
        return ReportOut(report_id=report_id, segment_id=sid, outcome=outcome.value, segment_status=status)

    @app.post("/segments/{segment_id}/votes", response_model=VoteOut)
    def vote(request: Request, segment_id: str, body: VoteIn, user_id: UserId) -> VoteOut:
        state = _state(request)
        if segment_id not in state.segments:
            raise HTTPException(status_code=404, detail=f"No sidewalk segment with id {segment_id}.")
        distance_m = state.segments.distance_m(segment_id, body.lat, body.lon)
        if distance_m > NEARBY_RADIUS_M:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"You need to be within {NEARBY_RADIUS_M} m of this sidewalk to vote on it "
                    f"(you're {distance_m:.0f} m away)."
                ),
            )
        segment = _key(state, segment_id)
        with state.lock:
            outcome = state.reports.vote(segment, user_id, body.blocked, datetime.now(UTC))
            status = state.reports.status(segment)
        return VoteOut(outcome=outcome.value, segment_status=status)

    @app.get("/segments/nearby", response_model=list[NearbySegmentOut])
    def nearby_segments(request: Request, lat: Latitude, lon: Longitude) -> list[NearbySegmentOut]:
        state = _state(request)
        close = state.segments.within(lat, lon, NEARBY_RADIUS_M)
        with state.lock:
            reported = {_sid(key): state.reports.status(key) for key in state.reports.reported_segments()}
        found = sorted((distance, sid) for sid, distance in close.items() if sid in reported)
        return [
            NearbySegmentOut(segment_id=sid, status=reported[sid], coordinates=state.segments.coordinates(sid))
            for _, sid in found
        ]

    @app.get("/reports", response_model=list[ReportListItem])
    def list_reports(request: Request) -> list[ReportListItem]:
        state = _state(request)
        with state.lock:
            book = state.reports
            # A confirmed photo stops being shown once votes reopen its segment:
            # drawing it would contradict the segment's current status.
            listed: list[tuple[PhotoReport, Verification]] = [
                (r, "confirmed") for r in book.confirmed_reports() if book.status(r.segment) is SegmentStatus.BLOCKED
            ]
            listed += [(r, "unverified") for r in book.unverified_reports()]
            listed += [(r, "pending") for r in book.pending_reports()]
        listed.sort(key=lambda item: item[0].reported_at, reverse=True)  # newest first
        items = []
        for report, verification in listed:
            sid = _sid(report.segment)
            if sid not in state.segments:
                continue  # not on this graph; can't place it on the map
            items.append(
                ReportListItem(
                    report_id=report.report_id,
                    segment_id=sid,
                    location=state.segments.midpoint(sid),
                    verification=verification,
                    reported_at=_iso_utc(report.reported_at),
                    simulated=False,  # no simulated demo reports yet
                )
            )
        return items

    return app


def image_type(data: bytes) -> str | None:
    """Media type from the file's first bytes, or None if it isn't JPEG, PNG or WebP.

    The client's filename and Content-Type are ignored: they're easy to get wrong.
    """
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _review(review_photo: PhotoReviewer, photo: bytes) -> PhotoVerdict:
    """A reviewer that crashes counts as unavailable: the report waits as pending."""
    try:
        return review_photo(photo)
    except Exception:
        logger.exception("Photo reviewer failed; keeping the report pending")
        return PhotoVerdict.UNAVAILABLE


def _state(request: Request) -> _State:
    return request.app.state.lumi


def _key(state: _State, sid: str) -> SegmentKey:
    return segment_key(*state.segments.endpoints(sid))


def _sid(key: SegmentKey) -> str:
    nodes = sorted(key)
    return make_segment_id(nodes[0], nodes[-1])


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
