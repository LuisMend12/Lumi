# Lumi teammate handoff

Lumi compares winter walking routes around BU and lets signed-in users report blocked sidewalks. Start by rehearsing the block and reopen flow locally. Then split the remaining work between the phone experience and the deployed services.

The [GitHub work summary](github-queue.md) explains each open PR and issue, including the order for the dependent UI PRs and what to verify before the demo.

## Run the local demo

Use Node.js 22.18+ and uv. From the repo root, run each block in a separate PowerShell terminal.

```powershell
cd backend
uv sync
$env:LUMI_DEMO_MODE = "1"
uv run uvicorn app.main:app --reload
```

This starts the backend at http://127.0.0.1:8000. Use a fresh terminal without exported PG settings for an in-memory rehearsal. If you need settings from `backend/.env`, add `--env-file .env` before `uvicorn`. Check `/health` for readiness and `/docs` for the live API schema.

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Before starting Next.js, fill in the Clerk keys in `frontend/.env.local` using [frontend/.env.example](../../frontend/.env.example) as the template. Open http://localhost:3000, which matches the backend's default CORS origin. Use the real local API for rehearsal, with `NEXT_PUBLIC_USE_MOCKS` unset. Visitors can browse without signing in.

## Rehearse the route change

1. Pick two BU landmarks inside the coverage area and compare Shortest, Safer, and Accessible. Use a route with a visible detour available.
2. In the Demo panel, choose **Block a sidewalk on this route**. Check that the report is labeled **Simulated** and that routes using the segment reroute or show a no-route message.
3. Cast four simulated votes to reopen that segment. Check that the route can use it again, then select **Reset demo** to remove simulated reports.

The simulation runs without Gemini or a database. Use `LUMI_DEMO_MODE=1` only in a controlled rehearsal environment because its write endpoints are available without sign-in.

## Split the next pass

| Owner | Pick up | Done when |
|---|---|---|
| Frontend | Rehearse on a phone and record the landmark pair. Check the map, mode explanations, location opt-in, and report and vote feedback. | The route, simulated block, detour, and reopening are easy to see. Accessible copy describes the mapped stair avoidance and the missing curb-ramp and slope data. |
| Backend | Verify Clerk, Mastra/Gemini, and Tiger Data together. Use a demo photo without identifiable people. | A signed-in upload returns an outcome, a confirmed block changes routing, and the block survives a backend restart. An unavailable reviewer produces a pending report. |
| Together | Run the hosted flow over HTTPS and agree on the demo sequence. | A phone can open the site, grant location access, and complete the rehearsal. |

For real report writes, configure `CLERK_ISSUER` and `CLERK_JWKS_URL` in the backend and start Mastra with its Gemini key. For persistence, use the current Tiger Data credentials in `backend/.env`. Confirm rotation of the previously exposed database password with the account owner before relying on the shared database. See the [backend setup](../../backend/README.md), [Mastra setup](../../mastra/README.md), and [deployment checklist](deploy.md).

## Where to make changes

| Area | Entry points |
|---|---|
| Map, route selection, and polling | `frontend/app/page.tsx`, `frontend/components/RouteMap.tsx` |
| Report form, nearby prompt, and demo controls | `frontend/components/ReportSheet.tsx`, `NearbyPrompt.tsx`, `DemoPanel.tsx` |
| API and payloads | `backend/app/main.py`, [API contract](api-contract.md) |
| Routing, report rules, and persistence | `backend/app/routing.py`, `reports.py`, `storage.py` |

Run `uv run pytest` from `backend/` and `npm.cmd run lint` from `frontend/` before opening a PR. Coordinate changes to shared payloads in the same PR as the API contract update.
