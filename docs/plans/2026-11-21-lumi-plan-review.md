# Review of the Lumi plan (2026-11-21)

Reviewed [the plan](2026-11-21-lumi-plan.md), `README.md`, `backend/app/` and `backend/scripts/try_vision.py`. I ran the tests (18 passed) and inspected `bu_walk.graphml` directly. Two corrections to the plan header: the backend is already committed (`6043d13` to `c290df9`), and the OSMnx cache file `backend/cache/*.json` is tracked. It should go in `.gitignore`.

## 1. Decided items: real problems only

- **#5 Accessible mode:** worse than the plan says. Accessible routes can use stairs, because the graph has 130 `highway=steps` edges and nothing excludes them. This breaks the rule against implying accessibility. It's cheap to fix: return `None` for steps in the Accessible weight, since the tag is already on each edge.
- **#3 In-memory hazards:** fine, but once reports live in TigerData, `POST /reports` must also update the in-memory dict. Run a single uvicorn worker, or each worker routes on its own stale copy.
- **#8 TigerData, PostGIS unverified:** you don't need PostGIS. Store lat/lon plus the snapped segment `(u, v)`, computed in Python when the report is written. That removes the risk.
- **#6 Vision:** the SDK usage (`messages.parse`, `output_format`, `parsed_output`) is correct. However, `severity` has no "none" value, so the model has to give a severity even for photos that aren't hazards. When you wire it in, handle `stop_reason == "refusal"` the same way as an AI failure.

## 2. Open decisions: recommendations

1. **Who sets `blocked`:** a clearly labeled demo/admin control, plus human-confirmed reports. Skip "several agreeing reports", because 36 hours won't produce enough users to test it. *Risk:* the demo looks staged unless the label is visible.
2. **What AI output does:** treat it as an unverified hazard that raises Safer/Accessible cost at a discount (for example, severity × 0.5), and show it on the map as "AI prediction". *Risk:* a wrong prediction causes an unneeded detour. The discount limits the harm, and it never blocks a segment.
3. **Fields:** keep `is_sidewalk_hazard`, `kind`, `severity` (mapped to 0.3 / 0.6 / 1.0), `confidence`, `accessibility_issue` and `description`. Store `blocked` as a suggestion only, never applied. Make `severity` nullable. *Risk:* low.
4. **Report flow:** **B, a single request.** It's the fewest moving parts. A adds a second endpoint and draft state in the UI, and C adds a background worker. *Risk:* the vision call takes several seconds, so set a timeout, show a spinner, and save with `analysis_status=failed` when it fails.
5. **Expiry:** a fixed time limit per kind (for example, slush 12 h, ice 24 h, obstruction 48 h), filtered when hazards are loaded. A "cleared" button can come later. *Risk:* the limits are arbitrary, which is fine for a demo.
6. **Photos:** cap uploads at 5 MB (the API's image limit) and downscale on the client. Strip EXIF before storing, keep photos only for the event, and add a simple per-IP rate limit on `/reports`. *Risk:* photos may show faces, so don't make them public by default.
7. **Unparked:** Next.js + Leaflet (no map token needed). Drop Mastra unless a prize depends on it. GoDaddy can wait until the deploy step.

## 3. Known issues check

| Issue | Verdict |
|---|---|
| Straight-line routes | **Confirmed.** 8,556 of 14,936 edges have curved `geometry`, which `routing.py:104` ignores. |
| Parallel edges | **Partly right.** 204 node pairs have parallel edges. Hazards are keyed by node pair, so a hazard on one edge blocks *both*. The real failure is losing a clear parallel path, not being unable to target an edge. |
| Snap to intersection | **Confirmed.** When both points snap to the same node, the API returns a 200 with one point and 0 m. The 422 message says "nearest mapped sidewalk" but measures to the nearest intersection. |
| `severity` unchecked | **Confirmed.** A severity below −0.25 gives a negative cost, so Dijkstra raises an error or returns a wrong path, which surfaces as a 500. Clamp it to [0, 1] and reject NaN. |
| Centerline vs. sidewalks | **Mostly resolved.** 11,356 edges are `highway=footway`, so most sidewalks are mapped separately. About 3,100 road edges are still centerlines. On Comm Ave, 22 edges are footway and 6 are primary road. Spot-check the demo street. |
| Accessible = Safer | **Confirmed**, and it also uses stairs (see §1). |

**Missing:**
- **High:** stairs in Accessible routes.
- **Medium:** there's no CORS middleware in `main.py`, so the frontend will fail on a different origin.
- **Medium:** `HazardOut` has no location, so the UI can't place warnings along the route.
- **Medium:** `Hazard` has no provenance fields (source, time, verification, simulated), which both the brief and expiry need.
- **Low:** 2,813 `service` edges (driveways, parking aisles) and 60 indoor `corridor` edges, so routes may cut through parking lots or buildings.

## 4. Build order

The order is realistic if step 1 takes about 2 hours or less and the frontend starts **in parallel** with step 2, since it only needs `/route`, which works today. Fix these before the demo: curved geometry, stairs in Accessible, the severity clamp, and CORS. Defer parallel edges, and handle the snap leg by drawing a dashed line from the user's point on the frontend. **Cut first:** Mastra, agreeing-reports logic, the async flow, expiry beyond fixed time limits, and all-of-Boston coverage.
