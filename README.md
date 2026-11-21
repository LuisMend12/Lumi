# Lumi

**Smarter paths. Safer winters.**

Winter walking navigation for Boston. Lumi recommends walking routes that account for reported snow, ice, and blocked sidewalks, not just distance. Built for HackBoston.

> **Status:** early. The routing backend works for a 1.5 km area around Boston University. Hazard reports, the frontend, and photo analysis are not built yet.

## What works today

- A walking network of 5,574 intersections and 14,936 sidewalk segments, within 1.5 km of Marsh Plaza (BU), from OpenStreetMap.
- `GET /route` with three modes: **shortest**, **safer**, **accessible**.
- Every mode skips segments reported fully blocked. Safer and Accessible also detour around milder hazards (snow, ice).
- Every response includes a plain-language explanation of what the chosen mode means.
- Points outside the coverage area are rejected with a clear message.

Hazard reports are not stored yet: the hazard list is empty while the server runs, so all three modes currently return the same route.

## Run the backend

Requires [uv](https://docs.astral.sh/uv/). It installs Python 3.12 automatically.

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs to try the API. Example, Marsh Plaza to Kenmore Square:

```
GET http://127.0.0.1:8000/route?start_lat=42.3504&start_lon=-71.1060&end_lat=42.3489&end_lon=-71.0951&mode=safer
```

Response:

```json
{
  "mode": "safer",
  "mode_description": "Safer: detours around reported snow, ice, ...",
  "distance_m": 951.7,
  "coordinates": [[42.3504, -71.1060], "..."],
  "hazards": []
}
```

| Status | Meaning |
|---|---|
| 200 | Route found. `hazards` lists anything reported on the segments it still uses. |
| 404 | No route avoids the blocked sidewalks. |
| 422 | Invalid input, or a point is outside the coverage area. |

### Tests

```bash
cd backend
uv run pytest
```

The tests use a tiny fake street network, so they run without the real map.

### Rebuild or resize the map

The coverage area is set in `backend/app/config.py` (`AREA_CENTER_LAT`, `AREA_CENTER_LON`, `AREA_RADIUS_M`). After changing it:

```bash
cd backend
uv run python scripts/build_graph.py
```

This downloads from OpenStreetMap and overwrites `backend/data/bu_walk.graphml`.

## How routing works

```
startup:  data/bu_walk.graphml ──load──> street graph in memory (never modified)
                                         hazards dict (empty for now; reports will fill it)

/route:   snap start/end to nearest intersection
          ──> Dijkstra with a weight function that combines graph + hazards ──> route
```

The street graph never changes. Hazard reports are kept separately, and a weight function combines the two on every request (`backend/app/routing.py`):

- **Blocked segment:** skipped by every mode.
- **Shortest:** cost = length.
- **Safer / Accessible:** cost = length × (1 + 4 × risk), where risk is the highest severity reported on that segment (0 to 1). The factor 4 is `SAFER_RISK_WEIGHT` in `config.py`, a starting value to tune.

Keeping all routing logic in that one function means adding modes or making old reports count less only changes one place.

## Project layout

```
backend/
  app/config.py          coverage area, file paths, tuning constants
  app/routing.py         modes, hazards, weight function, route search, point snapping
  app/main.py            FastAPI app: /health, /route
  scripts/build_graph.py downloads the street graph
  data/bu_walk.graphml   the street graph (committed so nobody has to re-download)
  tests/                 routing and API tests
```

## Decisions so far

| Decision | Choice |
|---|---|
| Demo area | 1.5 km around Marsh Plaza; extend to all of Boston later |
| Backend | Python + FastAPI |
| Routing state | Street graph unchanged; hazards combined when each route is computed |
| Blocked segments | Skipped in every mode |
| Mode explanations | Shown to the user with every route |
| Hazard report storage | TigerData (managed PostgreSQL), not wired up yet |

## Next up

1. **Hazard reports:** `POST /reports`, stored in TigerData, loaded into the hazards dict. Open question: how much evidence should it take before a segment counts as fully blocked?
2. **Frontend:** a Next.js map that draws routes from `/route`.
3. **Photo analysis:** a vision model that drafts a hazard report from an uploaded photo.

Later: Mastra (AI agent), a GoDaddy domain plus hosting, other sponsor tools, and weather-based predictions.

## Known limitations

- Hazard reports aren't implemented, so routes currently ignore real conditions.
- Accessible mode has no curb ramp or slope data yet; it treats hazards the same way Safer does.
- Points snap to the nearest intersection, not the nearest point along a sidewalk.
- Never present a route as "safe": reports can be missing or out of date.
