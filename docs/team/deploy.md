# Deploying Lumi

**For:** whoever deploys Lumi before the demo (issue #15). Nothing is deployed yet, and no host is chosen. This page lists what has to run, what each piece needs, and the order to bring it up in.

## What runs where

| Piece | What it is | Suggested host | Needs |
|---|---|---|---|
| **Backend** | FastAPI in `backend/`, Docker image from `backend/Dockerfile` | An always-on VM or container host (e.g. Vultr) | about 0.5 GB RAM, port 8000, HTTPS in front |
| **Photo agent** | Mastra service in `mastra/`, calls Gemini | Same server as the backend | Node 22, a Gemini API key |
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
| `LUMI_MASTRA_URL` | backend | URL of the Mastra service, e.g. `http://127.0.0.1:4111` on the same server |
| `CLERK_ISSUER` | backend | Clerk dashboard → API keys → **Frontend API URL**, e.g. `https://<name>.clerk.accounts.dev`. Public. Without it (or `CLERK_JWKS_URL`), reports and votes answer 503 |
| `CLERK_JWKS_URL` | backend | `<CLERK_ISSUER>/.well-known/jwks.json`. Public. The backend checks sign-in tokens against it, so it needs no Clerk secret |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | frontend | Clerk dashboard → API keys (`pk_…`). Public, and baked in at build time: rebuild after changing it |
| `CLERK_SECRET_KEY` | frontend | Clerk dashboard → API keys (`sk_…`). **Secret.** Set it only in the frontend host's environment settings, never in a file in the repo |
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
   **Keep port 4111 private.** Besides `/review`, Mastra serves its own built-in agent endpoints (and Studio), so anyone who can reach it can spend our Gemini quota. Run it on the same server as the backend, and don't open 4111 in the firewall or publish it from Docker. Only the backend talks to it, over `127.0.0.1`.
4. **Frontend:** deploy with `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY` set, then add its URL to `LUMI_FRONTEND_ORIGINS` and restart the backend.
5. **Clerk:** in the Clerk dashboard for the same instance as the keys:
   - add the deployed frontend domain to the allowed origins (Configure → Domains, or the instance's allowed origins);
   - check that **Google** and **email** sign-in are both enabled (Configure → User & authentication).

   A development instance (`pk_test_…`) shows a small "Development mode" badge; that's fine for the demo. A production instance needs its own keys and a domain you own.
6. **Smoke test from a real phone** (not a laptop):
   - [ ] The map loads and the coverage circle shows
   - [ ] Tapping start and end gives three routes
   - [ ] Location permission prompt appears (proves HTTPS works)
   - [ ] Signing in works with Google and with email
   - [ ] Taking a photo and submitting a report gets an outcome back
   - [ ] Restarting the backend keeps a blocked segment blocked (proves the database works)

## When something breaks

| Symptom | Likely cause |
|---|---|
| Browser console says "CORS" | `LUMI_FRONTEND_ORIGINS` is missing the exact frontend URL (scheme and no trailing slash) |
| "Mixed content" or requests blocked | The backend is plain `http://` |
| No location prompt | The page isn't on HTTPS |
| Reports always "under review" (pending) | The Mastra service is down, `LUMI_MASTRA_URL` is wrong, or the Gemini key is missing or rate-limited |
| Reports and votes answer 503 "sign-in isn't set up" | `CLERK_ISSUER` or `CLERK_JWKS_URL` is missing on the backend |
| Reports and votes answer 401 after signing in | `CLERK_ISSUER` doesn't match the instance the frontend keys belong to, or the frontend URL isn't in `LUMI_FRONTEND_ORIGINS` (the backend checks the token's origin) |
| Clerk says "outdated version of Clerk" | `@clerk/nextjs` is too old; see #76 |
| Backend restarts in a loop | `PGHOST` is set but the database is unreachable or the password is wrong |

Roll back by redeploying the previous image or commit. The database schema only adds tables, so older backends still run against it.

## Status of this page

- **Docker image verified on 2026-11-22** (from `main` after #25):
  - It builds in about 50 s and is 1.19 GB.
  - It answers `/health` about 4 s after start, the Docker health check reports healthy, and it uses about 194 MiB idle.
  - The demo route matches the demo script: Shortest 870.6 m, Accessible 1085.0 m.
  - That run had no `PGHOST`, so reports were kept in memory. The Tiger Data connection hasn't been checked from the container yet (#1).
- Storage (#30) and the Mastra photo agent (#26) are merged. Update this page if their settings change.
