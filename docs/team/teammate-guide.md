# Working on Lumi together: guide for the frontend lane

This is for you, the teammate building the frontend. It explains who does what for the rest of the hackathon, how we keep track of work, and what we need you to decide. Your Claude has its own guide, [claude-guide.md](claude-guide.md), with the technical details, so you don't need to read that one.

**Reading time:** about 5 minutes. The questions at the end matter most.

## First, one urgent thing

The Tiger Data password is on GitHub. `tiger/tiger-cloud-db-22859-credentials.env` was committed in `5afc888`. Adding `*.env` to `.gitignore` was the right instinct, but git keeps tracking a file it already has, and the password stays in the history even after the file is removed.

**If you own the Tiger Cloud account, please change the database password now.** Put the new one in `backend/.env`, which git ignores, and don't commit it. Your teammate will remove the old file from the repo. It's tracked in issue #1.

## Who does what

You've already built a lot: the report rules, CORS, curved routes and the map. From here we split by folder, so the two of us almost never edit the same files.

| Lane | Who | Folder | Owns |
|---|---|---|---|
| **Frontend** | **you** | `frontend/` | Map, route comparison, report flow, everything a user sees |
| **Backend** | your teammate | `backend/` | Routing fixes, report endpoints, photo review, Tiger Data storage |
| **Shared** | both | `docs/`, `.github/`, root files | API contract, login, deploy, demo |

Your teammate will build the backend pieces you depend on (the report endpoints, and the new fields on `/route`). So you don't have to wait for them, **build against [the API contract](api-contract.md) using mock data**, then switch to the real API once each backend PR is merged.

## The work, in order

Both lanes run at the same time. Arrows show what waits for what.

| Phase | You (frontend) | Teammate (backend) | Shared |
|---|---|---|---|
| **0. Now** (30 min) | Change the Tiger password (#1) | Untrack the credentials and the cache (#1, #4) | Agree the [API contract](api-contract.md) and answer the questions below |
| **1** | Pick the demo route (#8) | Stairs, severity and snapping fixes (#2, #3, #5) | |
| **2** | Route view: hazard markers, snap legs, Accessible note (#12), using mocks | Hazard locations on `/route` (#6), report endpoints (#9) | |
| **3** | Report flow UI (#13), using mocks, then the real API | Photo review with Claude (#10), Tiger Data storage (#11) | Decide on login (#14) |
| **4** | | | Deploy, domain, rehearse the demo (#15) |

#7 (parallel segments) is parked as low priority.

## How we track work

Every piece of work goes through the same loop. That way the issue explains *what was wrong*, and the PR explains *how it was fixed*.

1. **Issue:** each problem or task has a GitHub issue. Write new ones with the "Problem" or "Task" template, and say what's wrong and how you know.
2. **Branch:** one per issue, cut from an up-to-date `main`. Name it `fix/<issue number>-<short-name>` or `feat/<issue number>-<short-name>`, for example `feat/12-route-markers`.
3. **PR:** open it early. The template asks for Problem, Cause, Fix, How I tested and Follow-ups, and **that write-up is our record of how each thing was fixed**. Put `Closes #N` at the top so merging closes the issue.
4. **Merge:** once the tests pass and the other person has looked at it (see question 7). Delete the branch afterwards.

Pull `main` into your branch every few hours. Keep each branch to a few hours of work, because small PRs rarely conflict.

## Decided since your plan (please confirm)

- **Photo review stays a Claude vision call inside FastAPI, not a Mastra service.** That means one backend to deploy, no TypeScript agent server, and no Mastra prize. Your plan had this open (§2 item 12). Your teammate chose this, so please object now if you disagree.
- **Tiger Data is the one sponsor prize we go deep on.** It's already our database, and reports are time-stamped events. We skip Gemini, Solana, SpaceXSI and Mastra rather than bolting them on.

## Questions for you

Please answer in the docs PR, or on the issue named in brackets. Short answers are fine.

**Decisions only you can make:**
1. Do you own the Tiger Cloud account? If so, have you rotated the password yet? (#1)
2. Is moving photo review from Mastra to Claude in FastAPI OK with you?
3. Which login provider: Supabase Auth, Clerk, or a simple token from FastAPI? Or none for the demo, with clearly labeled simulated users? (#14)

**About the API contract** ([api-contract.md](api-contract.md)):

4. Does the shape work for the UI you have in mind? In particular, is `segment_id` as `"<u>-<v>"` fine, and is one `verification` field (`confirmed` / `unverified` / `pending`) enough to label reports?
5. Do you want the backend to return walking time, or keep computing it in `lib/modes.ts` as you do now?

**About the demo:**

6. The "4 different nearby users" rule can't happen live with two phones. Should the demo use **labeled simulated voters**, triggered by a button only we can see?
7. Should every PR be reviewed by the other person, or can small fixes be merged once tests pass? Reviewing everything is safer, but it slows us both down.
8. Where do you want to deploy the frontend: Vercel, the same Vultr server as the backend, or somewhere else? (#15)
9. Do you have a domain name in mind?

**About scope:**

10. Should unverified reports of snow or ice make Safer mode avoid a street, or only show on the map? Today, only confirmed blocks change routes.
11. Should a block expire if nobody answers "still blocked?" for a while? If so, after how long?
12. Is there anything in your lane you'd rather hand to your teammate, or the other way round?
