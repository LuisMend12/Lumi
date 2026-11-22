# Lumi: guide for Claude (either lane)

You're helping one of two people build Lumi in parallel. One person owns `backend/` and the other owns `frontend/`. Before starting, ask your human which lane they're in, unless they've already told you. The human-facing version of this plan is [teammate-guide.md](teammate-guide.md).

## Read first, in this order

1. This file.
2. [api-contract.md](api-contract.md): the HTTP contract between the two lanes. It's **proposed** until both humans approve the docs PR.
3. [../plans/2026-11-21-lumi-plan.md](../plans/2026-11-21-lumi-plan.md): product decisions (§2) and open questions (§4).
4. [../plans/2026-11-21-lumi-plan-review.md](../plans/2026-11-21-lumi-plan-review.md): the review written before the report rules existed. Its §2 recommendations on who sets `blocked` are **superseded** by plan §2 item 9. Its findings about the code and the graph still hold.
5. The open issues: `gh issue list`.

## Current state (2026-11-21)

- **Backend** (`backend/`):
  - `/route` already does three modes, curved route geometry and CORS for `http://localhost:3000` (GET only).
  - `app/reports.py` holds the report rules (photo confirm, 4-user flip, abuse limit), in memory, with a pluggable `PhotoReviewer`.
  - 40 tests pass: `cd backend && uv run pytest`.
- **Frontend** (`frontend/`): Next.js 15, React 19, Tailwind 4 and react-leaflet. You tap the start and end, it fetches all three modes and compares them. Run it with `cd frontend && npm install && npm run dev`, and set `NEXT_PUBLIC_API_URL` if the backend isn't on `127.0.0.1:8000`.
- **Not built yet:** the report endpoints, real photo review, storage, login and deployment.

## Lanes and file ownership

| Lane | Edit freely | Ask first |
|---|---|---|
| backend | `backend/**`, `mastra/**` (the photo-review agent service) | anything in `frontend/` |
| frontend | `frontend/**` | anything in `backend/` |
| shared | `docs/team/api-contract.md`, `.gitignore`, `README.md`, `.github/**` | always change these in their own small PR, and tell the other human |

If your lane needs a change in the other lane, open an issue for it. Don't edit the other folder.

## Workflow: one issue, one branch, one PR

```bash
git switch main && git pull --ff-only
git switch -c fix/<issue>-<slug>        # or feat/... or docs/...
# ... work, with tests ...
git commit -m "Short imperative summary (#<issue>)"
git push -u origin HEAD
gh pr create --title "<what the PR does>" --body-file <filled PR template>
```

- Start every PR body with `Closes #<issue>`, or `Part of #<issue>` if the issue stays open. Fill in every section of [the PR template](../../.github/pull_request_template.md). The **Cause** and **Fix** sections are how the team records how each problem was solved, so write them for a teammate who wasn't there. Say what you tried and dropped.
- If you find a new problem while working, **don't fix it quietly in the same PR**. Open a new issue with the Problem template (`gh issue create --template problem.md`, or write the body yourself in the same sections). Then mention it under the PR's Follow-ups.
- If you make or learn a decision, record it in plan §2 in the same PR, and say who decided it.
- Run the checks before pushing: `uv run pytest` for the backend, and `npm run lint` plus `npm run build` for the frontend.
- Don't merge without your human's go-ahead. Never force-push to `main`.

## Rules that apply in every lane

- **Never say a route is "safe"**, and never imply Accessible mode guarantees accessibility. Reuse the wording in `RouteMode` descriptions in `backend/app/routing.py`.
- Keep **confirmed**, **unverified** and **pending** reports separate, in storage, in the API and in the UI. Only confirmed blocks affect routing today. Simulated demo data always carries `simulated: true` and a visible badge.
- **AI never blocks a segment alone.** A photo blocks a segment only when a user reported it and the photo reviewer confirmed it (plan §2 items 7 and 9).
- **Secrets** go in `backend/.env` or `frontend/.env.local`, both ignored by git. Never commit them, never print their values, and stop and tell your human if you see one in a diff.
- **Decided:** photo review runs as a Mastra agent on Gemini's free tier; FastAPI calls it over HTTP (decided 2026-11-21 by both lanes). The agent is in `mastra/` (`POST /review`), and the confirm rule stays in `backend/app/photo_review.py`. The key goes in `mastra/.env`. Free-tier Gemini may use photos to improve Google's products, so test with photos without identifiable people.
- **Decided:** storage is Tiger Data. Don't depend on PostGIS. Store lat/lon and `segment_id` as plain columns.
- Don't add a dependency just to qualify for a sponsor prize.

## Lane notes

**Backend:** the next issues in order are #1, #4, #2, #3, #5, #6, #9, #10 and #11.
- `make_weight` in `routing.py` is the single place routing costs are set. Keep it that way.
- The street graph is loaded once and never changed. Hazards come from `SegmentReports.hazards()`.
- Test with the synthetic graph in `tests/conftest.py`, not the real graph.

**Frontend:** the next issues are #8 (the demo route), then #12 and #13.
- `lib/api.ts` is the only file that calls the backend. Add the new endpoints there first, with a mock switch (for example `NEXT_PUBLIC_USE_MOCKS=1`), so the UI can be built before the backend lands.
- Leaflet needs `window`, so keep map components loaded with `dynamic(..., { ssr: false })`, as `app/page.tsx` does.
- Phone-first: test at 375 px wide, and read location only while the app is open (plan §2 item 11).

## Ask your human before you

- change `docs/team/api-contract.md`, or any response shape the other lane uses;
- start work that an issue marks as "Decision needed" (for example login, #14);
- add a dependency, a new service, or anything that needs a new secret;
- delete or rewrite anything in git history, or touch the other lane's folder;
- run something that costs money (Gemini API calls on many photos, paid hosting).

## Useful questions to ask your human

- Which issue should I take next? Is anyone else already on it?
- Should this PR wait for the other person's review, or can it merge once tests pass?
- Is this a bug to fix now, or something to file as an issue for later?
- Does this wording on screen promise more than Lumi knows?
