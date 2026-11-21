"""Lumi API: street routing around Boston University."""

from contextlib import asynccontextmanager
from typing import Annotated

import networkx as nx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import FRONTEND_ORIGINS, GRAPH_PATH, MAX_SNAP_DISTANCE_M
from app.routing import Hazards, NoRouteError, RouteMode, find_route, nearest_node

Latitude = Annotated[float, Query(ge=-90, le=90)]
Longitude = Annotated[float, Query(ge=-180, le=180)]


class HazardOut(BaseModel):
    kind: str
    severity: float
    blocked: bool


class RouteOut(BaseModel):
    mode: RouteMode
    mode_description: str
    distance_m: float
    coordinates: list[tuple[float, float]]  # (lat, lon)
    snapped_start: tuple[float, float]  # (lat, lon) of the intersection the route starts at
    snapped_end: tuple[float, float]  # (lat, lon) of the intersection the route ends at
    hazards: list[HazardOut]


def load_street_graph() -> nx.DiGraph:
    import osmnx as ox  # heavy import; only needed for the real graph

    if not GRAPH_PATH.exists():
        raise RuntimeError(f"Street graph missing at {GRAPH_PATH}. Run: uv run python scripts/build_graph.py")
    return ox.convert.to_digraph(ox.load_graphml(GRAPH_PATH), weight="length")


def create_app(graph: nx.DiGraph | None = None, hazards: Hazards | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.graph = graph if graph is not None else load_street_graph()
        app.state.hazards = hazards if hazards is not None else {}
        yield

    app = FastAPI(title="Lumi API", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=FRONTEND_ORIGINS, allow_methods=["GET"])

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
        street_graph = request.app.state.graph
        start = _snap(street_graph, start_lat, start_lon, "Start")
        end = _snap(street_graph, end_lat, end_lon, "Destination")
        if start == end:
            raise HTTPException(
                status_code=422,
                detail="Start and destination are too close to route between. Pick points farther apart.",
            )
        try:
            result = find_route(street_graph, start, end, mode, request.app.state.hazards)
        except NoRouteError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return RouteOut(
            mode=mode,
            mode_description=mode.description,
            distance_m=round(result.distance_m, 1),
            coordinates=result.coordinates,
            snapped_start=_lat_lon(street_graph, start),
            snapped_end=_lat_lon(street_graph, end),
            hazards=[HazardOut(kind=h.kind, severity=h.severity, blocked=h.blocked) for h in result.hazards],
        )

    return app


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
