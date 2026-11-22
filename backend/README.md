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
| `LUMI_MASTRA_URL` | Where the photo-review service runs (`app/photo_review.py`) | No. Default `http://localhost:4111` |

The Gemini key isn't a backend variable: it goes in `mastra/.env` (see [mastra/README.md](../mastra/README.md)).

## Run

```bash
uv run uvicorn app.main:app --reload
```

Interactive docs: http://127.0.0.1:8000/docs

### Photo review service (Mastra)

Photo review runs in a separate Mastra service on Gemini's free tier, in `mastra/` at the repo root. The backend calls its `POST /review` endpoint through `make_mastra_reviewer()` in `app/photo_review.py`. In a second terminal:

```bash
cd mastra
npm install
cp .env.example .env    # then set GOOGLE_GENERATIVE_AI_API_KEY in mastra/.env
npm run dev             # http://localhost:4111
```

If the service is down or fails, photo reports stay pending and don't affect routing. The endpoint and error codes are in [mastra/README.md](../mastra/README.md). Gemini's free tier may use submitted photos to improve Google's products, so test with photos without identifiable people.

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

## How routing works

The street graph is loaded once at startup and never modified. Hazards are kept in a separate dict, keyed by segment, and the same key covers both walking directions. On each request, a weight function in `app/routing.py` combines the graph and the hazards:

- **Blocked segment:** skipped by every mode.
- **Shortest:** cost = length.
- **Safer / Accessible:** cost = length × (1 + `SAFER_RISK_WEIGHT` × risk). Risk is the highest severity reported on the segment, from 0 to 1.

The hazards dict is empty for now: hazard reports aren't implemented, so all three modes return the same route.

## Layout

```
app/
  config.py        coverage area, file paths, tuning constants
  routing.py       modes, Hazard, weight function, Dijkstra, point snapping
  reports.py       report rules: photo review, one-tap votes, 4-user flip, abuse limit (in memory, no endpoints yet)
  main.py          FastAPI app factory (create_app) and endpoints
scripts/
  build_graph.py   download the OSM walk network -> data/bu_walk.graphml
  try_photo_review.py  manual check: send a folder of photos through the Mastra reviewer
data/
  bu_walk.graphml  street graph (5,574 intersections, 14,936 segments)
tests/             pytest suite on a small synthetic graph
```

## Tests

```bash
uv run pytest
```

The tests build a tiny fake street network and pass it to `create_app(graph, hazards)`, so they don't load the real map or touch the network.

## Scripts

### Rebuild the street graph

To change the coverage area, edit `AREA_CENTER_LAT`, `AREA_CENTER_LON`, and `AREA_RADIUS_M` in `app/config.py`, then run:

```bash
uv run python scripts/build_graph.py
```

This downloads from OpenStreetMap and overwrites `data/bu_walk.graphml`.

### Try photo review on real photos

With the Mastra service running (see above):

```bash
uv run python scripts/try_photo_review.py path/to/photos
```

For each `.jpg`, `.png`, or `.webp` in the folder, this sends the photo through the Mastra service to Gemini and prints the structured assessment and the verdict the backend would give:

- `is_sidewalk_hazard`
- `kind`
- `severity`
- `blocked`
- `confidence`
- `accessibility_issue`
- `description`

Each photo is one Gemini call, which counts against the free tier's rate limits. The script is for judging how reliable the model is.

## Known issues

- Route lines connect intersections in straight lines and ignore the curve geometry stored in the graph (`app/routing.py`).
- When two paths connect the same pair of intersections, only the shortest is kept (`app/main.py`, `load_street_graph`).
- The stretch from the requested point to the snapped intersection isn't included in the route.
- `Hazard.severity` isn't range-checked.
- Accessible currently uses the same weights as Safer, because there's no curb-ramp or slope data.

More detail is in the plan doc's "Known issues" section.
