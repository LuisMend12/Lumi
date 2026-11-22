# Deploying Lumi

**For:** whoever deploys Lumi before the demo (issue #15). Nothing is deployed yet, and no host is chosen. This page lists what has to run, what each piece needs, and the order to bring it up in.

## What runs where

| Piece | What it is | Suggested host | Needs |
|---|---|---|---|
| **Backend** | FastAPI in `backend/`, Docker image from `backend/Dockerfile` | An always-on VM or container host (e.g. Vultr) | about 0.5 GB RAM, port 8000, HTTPS in front |
| **Photo agent** | Mastra service in `mastra/` (PR #26), calls Gemini | Same server as the backend | Node 22, a Gemini API key |
| **Frontend** | Next.js in `frontend/` | Vercel, or the same server | `NEXT_PUBLIC_API_URL` |
| **Database** | Tiger Data (managed Postgres + TimescaleDB) | Already hosted | The **rotated** password (#1) |

The backend keeps the street graph in memory. It loads in about 6 s at startup and peaks around 160 MB, so it needs a server that stays up, not a serverless function. Run **one worker**: report state lives in memory, so each extra worker would keep its own copy.

## HTTPS is required, not optional

Phones only allow **location** and the **camera** on HTTPS pages. If the frontend is on HTTPS (Vercel always is), the browser also blocks calls to an `http://` backend as mixed content. So the backend needs HTTPS too. Put a reverse proxy with automatic certificates (Caddy is the least setup) or the host's HTTPS in front of port 8000.

## Environment variables

Never commit real values. Each folder has a `.env.example` with the names.

| Variable | Where | Value |
|---|---|---|
| `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGSSLMODE` | backend | From the Tiger Cloud console, after rotating the password (#1). Without `PGHOST`, reports are kept in memory only and lost on restart. |
| `LUMI_FRONTEND_ORIGINS` | backend | The deployed frontend URL(s), comma-separated, e.g. `https://lumi.example.com`. Needed for CORS. Arrives with #25, which now includes the #28 report endpoints. |
| `LUMI_MASTRA_URL` | backend | URL of the Mastra service, e.g. `http://127.0.0.1:4111` on the same server (comes with #26) |
| Gemini key (name in `mastra/.env.example`) | Mastra | From Google AI Studio. Free tier: Google may use submitted content, so demo with photos that don't show people. |
| `NEXT_PUBLIC_API_URL` | frontend | The backend's public HTTPS URL. It's baked in at build time, so rebuild after changing it. |

## Bring-up order

1. **Database:** run `uv run python scripts/init_db.py` once from `backend/` with the rotated credentials in `backend/.env` (comes with #30). It's safe to re-run.
2. **Backend:**
   ```bash
   docker build -t lumi-backend backend
   docker run -d --restart unless-stopped -p 8000:8000 --env-file backend/.env --name lumi-backend lumi-backend
   ```
   Check it: `curl https://<backend>/health` should return `{"status":"ok"}`, which takes about 10 s after start.
3. **Photo agent:** start the Mastra service as described in `mastra/README.md`, then set `LUMI_MASTRA_URL` and restart the backend.
4. **Frontend:** deploy with `NEXT_PUBLIC_API_URL` set, then add its URL to `LUMI_FRONTEND_ORIGINS` and restart the backend.
5. **Smoke test from a real phone** (not a laptop):
   - [ ] The map loads and the coverage circle shows
   - [ ] Tapping start and end gives three routes
   - [ ] Location permission prompt appears (proves HTTPS works)
   - [ ] Taking a photo and submitting a report gets an outcome back
   - [ ] Restarting the backend keeps a blocked segment blocked (proves the database works)

## When something breaks

| Symptom | Likely cause |
|---|---|
| Browser console says "CORS" | `LUMI_FRONTEND_ORIGINS` is missing the exact frontend URL (scheme and no trailing slash) |
| "Mixed content" or requests blocked | The backend is plain `http://` |
| No location prompt | The page isn't on HTTPS |
| Reports always "under review" (pending) | The Mastra service is down, `LUMI_MASTRA_URL` is wrong, or the Gemini key is missing or rate-limited |
| Backend restarts in a loop | `PGHOST` is set but the database is unreachable or the password is wrong |

Roll back by redeploying the previous image or commit. The database schema only adds tables, so older backends still run against it.

## Status of this page

- `backend/Dockerfile` is written but **not test-built yet**: Docker Desktop's engine didn't start on the dev machine. Build it once before relying on it.
- The Mastra and storage parts depend on PRs #26 and #30. Update this page if they change.
