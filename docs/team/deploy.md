# Deploying Lumi

**For:** whoever deploys Lumi before the demo (issue #15). Nothing is deployed yet, and no host is chosen. This page lists what has to run, what each piece needs, and the order to bring it up in.

## What runs where

| Piece | What it is | Suggested host | Needs |
|---|---|---|---|
| **Backend** | FastAPI in `backend/`, Docker image from `backend/Dockerfile` | An always-on VM or container host (e.g. Vultr) | about 0.5 GB RAM, port 8000, HTTPS in front |
| **Photo agent** | Mastra service in `mastra/`, calls Gemini. Docker image from `mastra/Dockerfile` | Same server as the backend (`docker-compose.yml` runs both) | Node 22, a Gemini API key, no public port |
| **Frontend** | Next.js in `frontend/` | Vercel, or the same server | `NEXT_PUBLIC_API_URL` |
| **Database** | Tiger Data (managed Postgres + TimescaleDB) | Already hosted | The **rotated** password (#1) |

The backend keeps the street graph in memory. It loads in about 6 s at startup and peaks around 160 MB, so it needs a server that stays up, not a serverless function. Run **one worker**: report state lives in memory, so each extra worker would keep its own copy.

## HTTPS is required, not optional

Phones only allow **location** and the **camera** on HTTPS pages. If the frontend is on HTTPS (Vercel always is), the browser also blocks calls to an `http://` backend as mixed content. So the backend needs HTTPS too. Put a reverse proxy with automatic certificates (Caddy is the least setup) or the host's HTTPS in front of port 8000.

## One-command bring-up with Docker Compose

`docker-compose.yml` at the repo root runs the backend and the Mastra photo agent together on one server:

```bash
cp backend/.env.example backend/.env   # fill in PG*, CLERK_*, LUMI_FRONTEND_ORIGINS
cp mastra/.env.example mastra/.env     # fill in the Gemini key
docker compose up -d --build
docker compose ps                      # both should say (healthy) after about 10 s
curl http://localhost:8000/health      # {"status":"ok"}
```

- **What's published:** only the backend, on port 8000. Put HTTPS in front of it (see above). If the proxy runs on the same server, you can change the mapping to `127.0.0.1:8000:8000` so plain HTTP isn't reachable from outside.
- **What isn't:** Mastra (port 4111). It has no `ports:` entry, so only the backend reaches it, at `http://mastra:4111` on the compose network. Compose sets `LUMI_MASTRA_URL` to that and overrides whatever `backend/.env` says. Don't add a port mapping for it: besides `/review`, Mastra serves its built-in agent API and Studio (on `/`), so anyone who can reach it can spend our Gemini quota.
- **Env files are optional.** Without `backend/.env` the backend keeps reports in memory and reports and votes answer 503 (no Clerk). Without `mastra/.env` every photo review fails, so reports stay pending.
- **Demo mode:** `LUMI_DEMO_MODE=1 docker compose up -d` adds the `/demo` endpoints. Set it in the shell or in a repo-root `.env` (gitignored), not in `backend/.env`: the compose file sets `LUMI_DEMO_MODE` itself (default `0`), which overrides `backend/.env`.
- **Updates:** `git pull && docker compose up -d --build`. Logs: `docker compose logs -f backend mastra`. Stop: `docker compose down`.
- Both containers restart on their own (`restart: unless-stopped`) and have health checks: `GET /health` on each.
- The **frontend isn't in compose.** Deploy it separately (e.g. Vercel) with `NEXT_PUBLIC_API_URL` set to the backend's public HTTPS URL.

## Environment variables

Never commit real values. Each folder has a `.env.example` with the names.

| Variable | Where | Value |
|---|---|---|
| `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGSSLMODE` | backend | From the Tiger Cloud console, after rotating the password (#1). Without `PGHOST`, reports are kept in memory only and lost on restart. |
| `LUMI_FRONTEND_ORIGINS` | backend | The deployed frontend URL(s), comma-separated, e.g. `https://lumi.example.com`. Needed for CORS. Arrives with #25, which now includes the #28 report endpoints. |
| `LUMI_MASTRA_URL` | backend | URL of the Mastra service. Docker Compose sets it to `http://mastra:4111` for you; without compose, e.g. `http://127.0.0.1:4111` on the same server |
| `LUMI_DEMO_MODE` | backend | `1` adds the `/demo` endpoints for the demo script. With compose, set it in the shell or a repo-root `.env`, not in `backend/.env` |
| `CLERK_ISSUER` | backend | Clerk dashboard → API keys → **Frontend API URL**, e.g. `https://<name>.clerk.accounts.dev`. Public. Without it (or `CLERK_JWKS_URL`), reports and votes answer 503 |
| `CLERK_JWKS_URL` | backend | `<CLERK_ISSUER>/.well-known/jwks.json`. Public. The backend checks sign-in tokens against it, so it needs no Clerk secret |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | frontend | Clerk dashboard → API keys (`pk_…`). Public, and baked in at build time: rebuild after changing it |
| `CLERK_SECRET_KEY` | frontend | Clerk dashboard → API keys (`sk_…`). **Secret.** Set it only in the frontend host's environment settings, never in a file in the repo |
| Gemini key (name in `mastra/.env.example`) | Mastra | From Google AI Studio. Free tier: Google may use submitted content, so demo with photos that don't show people. |
| `NEXT_PUBLIC_API_URL` | frontend | The backend's public HTTPS URL. It's baked in at build time, so rebuild after changing it. |

## Bring-up order

1. **Database:** nothing to run. The backend creates the `reports` table (a TimescaleDB hypertable) and its index on startup, when `PG*` is set in `backend/.env`. It's safe on every restart.
2. **Backend and photo agent:** fill in `backend/.env` and `mastra/.env`, then `docker compose up -d --build` from the repo root (see [One-command bring-up](#one-command-bring-up-with-docker-compose)).
   Check it: `curl https://<backend>/health` should return `{"status":"ok"}`, which takes about 10 s after start.
   **Keep port 4111 private.** Besides `/review`, Mastra serves its own built-in agent endpoints (and Studio), so anyone who can reach it can spend our Gemini quota. Compose already keeps it off the host; don't add a port mapping for it or open 4111 in the firewall.
   <details><summary>Without compose</summary>

   ```bash
   docker build -t lumi-backend backend
   docker run -d --restart unless-stopped -p 8000:8000 --env-file backend/.env --name lumi-backend lumi-backend
   ```
   Then start the Mastra service as described in `mastra/README.md` on the same server, set `LUMI_MASTRA_URL` and restart the backend. Inside a container, `127.0.0.1` is the container itself, not the server, so a backend started with `-p` can't reach a Mastra on the server's `127.0.0.1:4111`. Compose avoids that.
   </details>
3. **Frontend:** deploy it separately (e.g. Vercel) with `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY` set. Then add its URL to `LUMI_FRONTEND_ORIGINS` in `backend/.env` and run `docker compose up -d` again (a plain `docker compose restart` doesn't re-read env files).
4. **Clerk:** in the Clerk dashboard for the same instance as the keys:
   - add the deployed frontend domain to the allowed origins (Configure → Domains, or the instance's allowed origins);
   - check that **Google** and **email** sign-in are both enabled (Configure → User & authentication).

   A development instance (`pk_test_…`) shows a small "Development mode" badge; that's fine for the demo. A production instance needs its own keys and a domain you own.
5. **Smoke test from a real phone** (not a laptop):
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
- **Docker Compose verified on 2026-11-22** (Docker Desktop, Compose v5.4, no env files, `LUMI_DEMO_MODE=1`):
  - `docker compose build` takes about 75 s from scratch. Images: backend 1.24 GB, Mastra 572 MB.
  - Both containers report healthy within about 5 s. Idle memory: backend about 207 MiB, Mastra about 116 MiB.
  - From inside the backend container, `POST http://mastra:4111/review` with a bad body returns Mastra's `400 invalid_request`. From the host, port 4111 refuses connections.
  - The demo flow matches the demo script: Warren Towers → Packard's Corner is 1631.3 m in all three modes, 1714.8 m after blocking the segment nearest `42.35036,-71.11120`, and back to 1631.3 m after 4 "not blocked" votes. Without `LUMI_DEMO_MODE`, `/demo/status` is 404.
  - Not checked: a real photo review through Gemini, the Tiger Data connection and Clerk sign-in from the containers.
- Storage (#30) and the Mastra photo agent (#26) are merged. Update this page if their settings change.
