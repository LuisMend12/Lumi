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

## The routes

**Main route: Warren Towers → Packard's Corner**, about 1 mile along the Comm Ave corridor (#8):

| | lat, lon | Where to tap |
|---|---|---|
| Start | `42.3490, -71.1040` | Warren Towers, Comm Ave just east of BU Central |
| End | `42.3518, -71.1230` | Packard's Corner, where Comm Ave meets Brighton Ave |

**Accessible moment: Questrom → St. Mary's Street T stop** (#8). The main route has no steps, so Accessible looks the same as the other modes there. This short route shows the difference:

| | lat, lon | Where to tap |
|---|---|---|
| Start | `42.34940, -71.09959` | Questrom, 595 Comm Ave |
| End | `42.34616, -71.10755` | St. Mary's Street T stop, Beacon St |

Shortest is **871 m** down the Blandford Street steps; Accessible is **1,085 m** and avoids them.

## Script

| # | Do | Say | You should see |
|---|---|---|---|
| 1 | Show the map | "Boston sidewalks in winter: snowbanks and ice make the shortest walk the wrong walk." | Map of BU with the dashed coverage circle |
| 2 | Tap the start, then the end | "Lumi gives three routes: Shortest, Safer, and Accessible, and says what each one means." | Three lines; cards around 1,631 m (≈20 min) |
| 3 | **Demo controls → Block a sidewalk on this route** | "Someone reports a snowbank halfway along. A person reports it; the AI only checks the photo. AI alone never blocks a sidewalk." | All three routes redraw around it, ≈1,715 m; a **Simulated** marker. (The button blocks the sidewalk nearest the route's halfway point.) |
| 4 | Point at the marker | "Every report says whether it's confirmed, unverified, or under review. Demo data is labeled Simulated." | Marker tooltip "Simulated · Report · Confirmed" |
| 5 | **4 bots say it's clear** | "To clear a block, four *different* signed-in people nearby have to say so, like Waze's closures. These four are simulated people." | Message "4 simulated people said it's clear…"; the route returns to ≈1,631 m |
| 6 | Optional: **Report blocked sidewalk** with a photo | "On a phone, you take a photo, and Lumi uses your location only while the app is open." | Photo sheet; outcome message. **On the laptop**, pick a photo file in the sheet. **A phone only works with the deployed HTTPS site** (#15): with this local setup, `localhost` on a phone means the phone itself, and phones only share location on HTTPS pages |
| 7 | **Reset demo**, then tap **Questrom**, then the **St. Mary's St T stop** | "Accessible skips stairs. Here the shortest walk goes down the Blandford Street steps." | Shortest ≈871 m; **Accessible ≈1,085 m** on a different path, with its limitation note: no curb-ramp data yet |

## Points to make honestly

- Routes are **never** called safe: reports can be missing or out of date.
- Simulated people and reports are always labeled.
- Known limits: locations are self-reported (#60), and there's no curb-ramp or slope data yet.
- Reports only mark a sidewalk **blocked** today. Milder hazards like ice are supported by the routing (Safer weighs them) but can't be reported in the app yet, so don't promise an "ice detour" in the demo.

## If something breaks

| Symptom | Do this |
|---|---|
| "Can't reach the Lumi server" | Backend isn't running or is still loading the map (about 6 s). Check terminal 1 |
| No Demo controls panel | The backend isn't in demo mode. Restart it with `LUMI_DEMO_MODE=1` |
| Report or vote says sign in again | Sign in from the header. Clerk tokens last about a minute and are refreshed per request |
| Photo stays "Under review" | Mastra or the Gemini key is down. Say: "the AI check is unavailable, so the report waits instead of changing routes. That's by design." (Retry is #53.) |
| "No route avoids the blocked sidewalks." | Press **Reset demo**. A leftover simulated block may cut every path |
| A second screen doesn't show the change | Wait up to 20 s: open pages refresh reports and routes every 20 s while visible (#59), or reload |
