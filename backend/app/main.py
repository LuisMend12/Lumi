"""Lumi API: street routing around Boston University."""

from contextlib import asynccontextmanager
from typing import Annotated

import networkx as nx
from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel

from app.config import GRAPH_PATH, MAX_SNAP_DISTANCE_M
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
        try:
            result = find_route(street_graph, start, end, mode, request.app.state.hazards)
        except NoRouteError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return RouteOut(
            mode=mode,
            mode_description=mode.description,
            distance_m=round(result.distance_m, 1),
            coordinates=result.coordinates,
            hazards=[HazardOut(kind=h.kind, severity=h.severity, blocked=h.blocked) for h in result.hazards],
        )

    return app


def _snap(graph: nx.DiGraph, lat: float, lon: float, label: str):
    node, distance_m = nearest_node(graph, lat, lon)
    if distance_m > MAX_SNAP_DISTANCE_M:
        raise HTTPException(
            status_code=422,
            detail=f"{label} is outside Lumi's coverage area ({distance_m:.0f} m from the nearest mapped sidewalk).",
        )
    return node


app = create_app()
