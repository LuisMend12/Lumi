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
| `LUMI_FRONTEND_ORIGINS` | CORS: comma-separated browser origins allowed to call the API | No; defaults to `http://localhost:3000` |
| `LUMI_MASTRA_URL` | Where the photo-review service runs (`app/photo_review.py`) | No. Default `http://localhost:4111` |
| `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGSSLMODE` | Storing reports in Tiger Data (standard libpq names) | No. Without `PGHOST`, reports are kept in memory and lost on restart |
| `LUMI_TEST_DATABASE_URL` | Running the Postgres store tests against a throwaway TimescaleDB database | No; those tests are skipped |

The Gemini key isn't a backend variable: it goes in `mastra/.env` (see [mastra/README.md](../mastra/README.md)).

To load `.env`, run the server with `uv run --env-file .env uvicorn app.main:app --reload`.

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
- `hazards`: reported hazards on the segments the route still uses, each with `location` (segment midpoint), `kind`, `severity` and `blocked`

| Status | Meaning |
|---|---|
| 200 | Route found |
| 404 | No route avoids the blocked sidewalks |
| 422 | Invalid input, or a point more than 250 m from the nearest mapped intersection |

`hazards` combines confirmed community reports (`app/reports.py`) with any hazards passed to `create_app` in tests.

### Reports

The full shapes are in [docs/team/api-contract.md](../docs/team/api-contract.md). Writes need a Clerk session token in `Authorization: Bearer <token>` (see `app/auth.py`). Without one they return `401`, and if `CLERK_ISSUER` / `CLERK_JWKS_URL` aren't set they return `503`. Reads need no sign-in.

| Endpoint | Success | Errors |
|---|---|---|
| `POST /reports` (multipart `lat`, `lon`, `photo`) | `201` with `outcome` `status_changed`, `vote_recorded`, `unverified` or `pending` | `401`, `413` photo over 5 MB, `415` not JPEG/PNG/WebP, `422` more than 250 m from any sidewalk |
| `POST /segments/{segment_id}/votes` (JSON `blocked`, `lat`, `lon`) | `200` with `outcome` `vote_recorded`, `status_changed` or `photo_required` | `401`, `403` more than 50 m from the segment, `404` unknown segment, `422` |
| `GET /segments/nearby?lat=&lon=` | `200`: reported segments within 50 m, closest first | `422` |
| `GET /reports` | `200`: confirmed, unverified and pending photo reports, newest first | |

A report is attached to the closest sidewalk segment, measured to the street's shape rather than to its intersections. The backend calls Mastra for photo review. If review is unavailable, the report stays `pending` and does not affect routing.

### Storage

Every photo report and counted vote is one row in Tiger Data's `reports` table, a TimescaleDB hypertable on `reported_at`. A photo report's row holds its `status` (`confirmed`, `unverified` or `pending`) and the photo itself; a vote's `status` is empty. Each write is saved before it's applied in memory; if saving fails, the API returns `503` and nothing changes. On startup, `app/storage.py` creates the table if it's missing, then replays the rows oldest first with their stored statuses, so segment status survives a restart and the photo reviewer isn't called again.

The schema is `SCHEMA` in `app/storage.py`. Reports don't expire yet.

## How routing works

The street graph is loaded once at startup and never modified. Hazards are kept in a separate dict, keyed by segment, and the same key covers both walking directions. On each request, a weight function in `app/routing.py` combines the graph and the hazards:

- **Blocked segment:** skipped by every mode.
- **Shortest:** cost = length.
- **Safer / Accessible:** cost = length × (1 + `SAFER_RISK_WEIGHT` × risk). Risk is the highest severity reported on the segment, from 0 to 1.

Hazards come from confirmed community reports. Accessible also avoids mapped stairs.

## Layout

```
app/
  config.py        coverage area, file paths, tuning constants
  routing.py       modes, Hazard, weight function, Dijkstra, point snapping
  reports.py       report rules: photo review, one-tap votes, 4-user flip, abuse limit (in memory)
  segments.py      segment lookup by id and nearest segment to a point
  storage.py       stored reports: Tiger Data and in-memory stores, schema, replay on startup
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

The tests build a tiny fake street network and pass it to `create_app(graph, hazards, review_photo, store)` with a fake photo reviewer and an in-memory store, so they don't load the real map, touch the network, call Claude or connect to a database. The Postgres store tests run only when `LUMI_TEST_DATABASE_URL` is set; they drop and recreate the `reports` table, so point it at a throwaway database.

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

- When two paths connect the same pair of intersections, only the shortest is kept (`app/main.py`, `load_street_graph`).
- The stretch from the requested point to the snapped intersection isn't included in the route.
- Accessible avoids mapped stairs and uses Safer's hazard weights. Curb-ramp and slope data are unavailable.

More detail is in the plan doc's "Known issues" section.
