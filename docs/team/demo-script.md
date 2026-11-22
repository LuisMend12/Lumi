# Lumi demo script

**For:** whoever presents Lumi. The demo takes about 4 minutes. Rehearse it twice, the second time with one failure (see "If something breaks").

## Before you start (10 minutes ahead)

1. **Backend in demo mode**, with Tiger Data and Clerk settings in `backend/.env`:
   ```powershell
   cd backend
   $env:LUMI_DEMO_MODE = "1"; uv run --env-file .env uvicorn app.main:app --port 8000
   ```
   Wait for `Uvicorn running on http://127.0.0.1:8000`. Check http://127.0.0.1:8000/demo/status shows `{"demo_mode":true}`.
2. **Frontend:** `cd frontend; npm run dev`, then open **http://localhost:3000**. Use `localhost`, not `127.0.0.1`, or CORS and sign-in fail.
3. **Clean slate:** in the amber **Demo controls** panel, press **Reset demo**. That removes simulated data only.
4. **Sign in once** (Google or email), so you don't hit the sign-in popup mid-demo.
5. Optional, for photo review: start the Mastra service (`mastra/README.md`) with a Gemini key. Without it, photo reports show "Under review", which is fine to explain.

## The route

**Warren Towers → Packard's Corner**, about 1 mile along the Comm Ave corridor (#8):

| | lat, lon | Where to tap |
|---|---|---|
| Start | `42.3490, -71.1040` | Warren Towers, Comm Ave just east of BU Central |
| End | `42.3518, -71.1230` | Packard's Corner, where Comm Ave meets Brighton Ave |

## Script

| # | Do | Say | You should see |
|---|---|---|---|
| 1 | Show the map | "Boston sidewalks in winter: snowbanks and ice make the shortest walk the wrong walk." | Map of BU with the dashed coverage circle |
| 2 | Tap the start, then the end | "Lumi gives three routes: Shortest, Safer, and Accessible, and says what each one means." | Three lines; cards around 1,631 m (≈20 min) |
| 3 | Select **Accessible** | "Accessible skips stairs. We don't have curb-ramp data yet, and the app says so up front." | Accessible card with its limitation note |
| 4 | **Demo controls → Block a sidewalk on this route** | "Someone reports a snowbank halfway along. A person reports it; the AI only checks the photo. AI alone never blocks a sidewalk." | Route redraws around it; Safer ≈1,715 m; a **Simulated** marker |
| 5 | Point at the marker | "Every report says whether it's confirmed, unverified, or under review. Demo data is labeled Simulated." | Marker tooltip "Simulated · Report · Confirmed" |
| 6 | **4 bots say it's clear** | "To clear a block, four *different* signed-in people nearby have to say so, like Waze's closures. These four are simulated people." | Message "4 simulated people said it's clear…"; the route returns to ≈1,631 m |
| 7 | Optional: **Report blocked sidewalk** on a phone | "On a phone, you take a photo, and Lumi uses your location only while the app is open." | Photo sheet; outcome message |
| 8 | **Reset demo** | — | "Demo reset: removed … simulated reports and votes" |

## Points to make honestly

- Routes are **never** called safe: reports can be missing or out of date.
- Simulated people and reports are always labeled.
- Known limits: locations are self-reported (#60), and there's no curb-ramp or slope data yet.

## If something breaks

| Symptom | Do this |
|---|---|
| "Can't reach the Lumi server" | Backend isn't running or is still loading the map (about 6 s). Check terminal 1 |
| No Demo controls panel | The backend isn't in demo mode. Restart it with `LUMI_DEMO_MODE=1` |
| Report or vote says sign in again | Sign in from the header. Clerk tokens last about a minute and are refreshed per request |
| Photo stays "Under review" | Mastra or the Gemini key is down. Say: "the AI check is unavailable, so the report waits instead of changing routes. That's by design." (Retry is #53.) |
| "No route found" | Press **Reset demo**. A leftover simulated block may cut every path |
| A phone doesn't show the change | Reload it. Other phones don't refresh automatically yet (#59) |
