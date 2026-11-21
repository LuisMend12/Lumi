# Lumi backend

FastAPI service that computes winter walking routes around Boston University. For the project overview, see the [root README](../README.md). Open design questions are in [docs/plans/2026-11-21-lumi-plan.md](../docs/plans/2026-11-21-lumi-plan.md).

## Setup

Requires [uv](https://docs.astral.sh/uv/). It installs Python 3.12 automatically.

```bash
cd backend
uv sync
```

The street graph `data/bu_walk.graphml` is committed, so you don't need to download anything.

### Environment variables

Put these in `backend/.env`, which is gitignored. Never commit keys.

| Variable | Needed for | Required now? |
|---|---|---|
| `ANTHROPIC_API_KEY` | `scripts/try_vision.py` (Claude vision) | Only to run the photo spike |
| `LUMI_FRONTEND_ORIGINS` | CORS: comma-separated browser origins allowed to call the API | No; defaults to `http://localhost:3000` |

## Run

```bash
uv run uvicorn app.main:app --reload
```

Interactive docs: http://127.0.0.1:8000/docs

## API

### `GET /health`

Returns `{"status": "ok"}`.

### `GET /route`

| Query param | Type | Notes |
|---|---|---|
| `start_lat`, `start_lon` | float | Start point |
| `end_lat`, `end_lon` | float | Destination |
| `mode` | `shortest` \| `safer` \| `accessible` | Default `safer` |

Example: Marsh Plaza to Kenmore Square.

```
GET /route?start_lat=42.3504&start_lon=-71.1060&end_lat=42.3489&end_lon=-71.0951&mode=safer
```

The response has these fields:

- `mode`
- `mode_description`: plain-language text to show the user
- `distance_m`
- `coordinates`: a list of `[lat, lon]` pairs in walking order
- `hazards`: reported hazards on the segments the route still uses

| Status | Meaning |
|---|---|
| 200 | Route found |
| 404 | No route avoids the blocked sidewalks |
| 422 | Invalid input, or a point more than 250 m from the nearest mapped intersection |

`hazards` combines confirmed community reports (`app/reports.py`) with any hazards passed to `create_app` in tests.

### Reports

The full shapes are in [docs/team/api-contract.md](../docs/team/api-contract.md). Writes need an `X-User-Id` header (any stable string until login exists); without it they return `401`.

| Endpoint | Success | Errors |
|---|---|---|
| `POST /reports` (multipart `lat`, `lon`, `photo`) | `201` with `outcome` `status_changed`, `vote_recorded`, `unverified` or `pending` | `401`, `413` photo over 5 MB, `415` not JPEG/PNG/WebP, `422` more than 250 m from any sidewalk |
| `POST /segments/{segment_id}/votes` (JSON `blocked`, `lat`, `lon`) | `200` with `outcome` `vote_recorded`, `status_changed` or `photo_required` | `401`, `403` more than 50 m from the segment, `404` unknown segment, `422` |
| `GET /segments/nearby?lat=&lon=` | `200`: reported segments within 50 m, closest first | `422` |
| `GET /reports` | `200`: confirmed, unverified and pending photo reports, newest first | |

A report is attached to the closest sidewalk segment, measured to the street's shape rather than to its intersections. No photo reviewer is wired in yet, so outside tests every photo report stays `pending` and doesn't affect routing. Reports are kept in memory and are lost on restart.

## How routing works

The street graph is loaded once at startup and never modified. Hazards are kept in a separate dict, keyed by segment, and the same key covers both walking directions. On each request, a weight function in `app/routing.py` combines the graph and the hazards:

- **Blocked segment:** skipped by every mode.
- **Shortest:** cost = length.
- **Safer / Accessible:** cost = length × (1 + `SAFER_RISK_WEIGHT` × risk). Risk is the highest severity reported on the segment, from 0 to 1.

Hazards come from confirmed community reports, so until someone reports a blockage all three modes return the same route.

## Layout

```
app/
  config.py        coverage area, file paths, tuning constants
  routing.py       modes, Hazard, weight function, Dijkstra, point snapping
  reports.py       report rules: photo review, one-tap votes, 4-user flip, abuse limit (in memory)
  segments.py      segment lookup by id and nearest segment to a point
  main.py          FastAPI app factory (create_app) and endpoints
scripts/
  build_graph.py   download the OSM walk network -> data/bu_walk.graphml
  try_vision.py    throwaway spike: Claude vision assessment of sidewalk photos
data/
  bu_walk.graphml  street graph (5,574 intersections, 14,936 segments)
tests/             pytest suite on a small synthetic graph
```

## Tests

```bash
uv run pytest
```

The tests build a tiny fake street network and pass it to `create_app(graph, hazards, review_photo)` with a fake photo reviewer, so they don't load the real map, touch the network or call Claude.

## Scripts

### Rebuild the street graph

To change the coverage area, edit `AREA_CENTER_LAT`, `AREA_CENTER_LON`, and `AREA_RADIUS_M` in `app/config.py`, then run:

```bash
uv run python scripts/build_graph.py
```

This downloads from OpenStreetMap and overwrites `data/bu_walk.graphml`.

### Photo-analysis spike

```bash
uv run --env-file .env python scripts/try_vision.py path/to/photos
```

For each `.jpg`, `.png`, or `.webp` in the folder, this sends the photo to `claude-opus-5-5` and prints a structured assessment:

- `is_sidewalk_hazard`
- `kind`
- `severity`
- `blocked`
- `confidence`
- `accessibility_issue`
- `description`

Each photo is one paid API call. The script is for judging how reliable the model is. It isn't wired into the API.

## Known issues

- Route lines connect intersections in straight lines and ignore the curve geometry stored in the graph (`app/routing.py`).
- When two paths connect the same pair of intersections, only the shortest is kept (`app/main.py`, `load_street_graph`).
- The stretch from the requested point to the snapped intersection isn't included in the route.
- `Hazard.severity` isn't range-checked.
- Accessible currently uses the same weights as Safer, because there's no curb-ramp or slope data.

More detail is in the plan doc's "Known issues" section.
