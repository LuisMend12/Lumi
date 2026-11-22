# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

**Primary:** BU students and staff walking around Boston University in winter, phone in hand (often gloved), choosing a route before or during a walk when snowbanks, ice, and slush make the shortest way the wrong way.

**Secondary:**
- People with mobility needs (wheelchair, walker, stroller), for whom one blocked sidewalk or staircase breaks the trip.
- Hackathon judges trying the app for a minute or two during a live demo.

## Product Purpose

Lumi is winter walking navigation for the area around BU (1.5 km around Marsh Plaza). It compares three walking routes, Shortest, Safer, and Accessible, and reroutes around sidewalks that people report as blocked. Success: a walker picks a route that avoids a reported snowbank before they reach it, and a blocked sidewalk visibly changes the recommended route.

## Positioning

Routes bend around what people actually report:
- A person reports a blocked sidewalk with a photo; an AI agent only checks the photo. AI alone never blocks a sidewalk.
- Four different signed-in people are needed to flip a sidewalk between blocked and clear.
- Nearby walkers answer a one-tap "still blocked?" question.
- Lumi never calls a route safe.

## Operating Context

- Used outdoors on a phone in cold weather, often mid-walk; also on laptops before leaving.
- The location is read only while the app is open and only after the user asks.
- Live hackathon demo: two phones on stage, a scripted 1-mile route (Warren Towers → Packard's Corner), simulated people triggered from a demo panel (`docs/team/demo-script.md`).

## Capabilities and Constraints

- **Modes:**
  - **Shortest:** the most direct walk; skips blocked sidewalks; may pass reported snow or ice.
  - **Safer:** detours around reported snow, ice, and blocked sidewalks when it can.
  - **Accessible:** avoids stairs and reported hazards; a start or end reachable only by stairs moves to the nearest step-free point, up to 100 m.
- **Reports:** photo report → AI check (Mastra agent on Gemini) → confirmed, unverified, or under review (pending, retried). One-tap votes from people within 50 m. An abuse limit asks heavy reporters for a photo.
- **Sign-in:** Clerk (Google, or email and password). Browsing needs no sign-in; reporting and voting do.
- **Data:** OpenStreetMap walk network; reports are stored in Tiger Data.
- **Known limits, stated honestly:**
  - no curb-ramp or slope data;
  - report and vote locations are self-reported;
  - coverage is limited to around BU.
- **Terms in the UI:** Shortest, Safer, Accessible; "Report blocked sidewalk"; "Still blocked" / "It's clear"; Confirmed / Unverified report / Under review; Simulated.
- **Undecided:** frontend hosting (Vercel planned) and the backend host.

## Brand Commitments

- Name: **Lumi**.
- Palette base is binding: **light blue, white, and navy** (team brief). The look should be bold and playful within it.
- Never present a route as safe. "Safer" stays as the mode name but is always defined.
- Simulated or demo data is always labeled "Simulated"; unverified or pending reports are never shown as fact.

## Evidence on Hand

- The real BU walk graph (`backend/data/bu_walk.graphml`) and real route results (e.g. demo route 1,631 m; 1,715 m after a block).
- No real users, testimonials, usage numbers, or press. Do not invent any.

## Product Principles

1. **People decide, AI checks.** No automated signal alone changes a route.
2. **Honest over reassuring.** Say what Lumi knows and doesn't; never promise safety.
3. **Fast in the cold.** The core job (pick a route) works in seconds, one-handed, without reading.
4. **Labeled always.** Every report shows its verification state; every simulated item says so.

## Accessibility & Inclusion

Routes and reports must work by keyboard and screen reader. Color is never the only signal: modes differ by dash pattern, and verification states by text label. Accessible mode must state its limits, with no curb-ramp or slope data yet.
