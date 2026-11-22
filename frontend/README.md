# Lumi frontend

The map website: click a start and a destination, and compare the Shortest, Safer, and Accessible walking routes.

Next.js 15 (App Router) + TypeScript + Tailwind CSS 4 + Leaflet (react-leaflet), with OpenStreetMap tiles. No map API key is needed.

## Run

The backend must be running too. See the [root README](../README.md#run-the-app) for both steps.

```bash
npm install   # first time only
npm run dev   # http://localhost:3000
```

| Command | What it does |
|---|---|
| `npm run dev` | Dev server with live reload |
| `npm run build` | Production build (also catches type errors) |
| `npm run lint` | ESLint |
| `npx tsc --noEmit` | Type check only |

## Configuration

Copy `.env.example` to `.env.local` and fill it in. The Clerk keys are required: without them the app won't start.

| Variable (in `.env.local`) | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://127.0.0.1:8000` | Where the backend runs |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | none (required) | Clerk sign-in. Public; it ships to the browser |
| `CLERK_SECRET_KEY` | none (required) | Clerk server key. **Secret**: never commit or share it. Clerk members copy it from the dashboard |
| `NEXT_PUBLIC_USE_MOCKS` | unset | Set to `true` to use sample data shaped like [the API contract](../docs/team/api-contract.md) instead of the backend. The page shows a "Mock data" banner while this is on |

`NEXT_PUBLIC_*` values are bundled into the browser code, so never put secrets in them.

## Layout

```
app/page.tsx             page state: clicked points, fetched routes, selected mode, mode cards
app/globals.css          winter palette (CSS variables)
components/RouteMap.tsx  Leaflet map, coverage circle, route lines, reports, nearby highlight (browser-only, loaded with ssr: false)
components/ReportSheet.tsx   photo report: take/choose photo, preview, submit, outcome message
components/NearbyPrompt.tsx  one-tap "Still blocked / It's clear" card for a nearby reported sidewalk
lib/api.ts               typed calls to GET /route, readable error messages
lib/reports-api.ts       report, vote, nearby, and reports endpoints; temporary X-User-Id
lib/reporting.ts         plain-language wording for every report and vote outcome
lib/device.ts            location (read only while the app is open) and in-browser photo shrinking
lib/mocks.ts             contract-shaped sample data (NEXT_PUBLIC_USE_MOCKS); report and vote calls cycle through every outcome
lib/modes.ts             coverage area, per-mode styles, verification labels, walking time
```

The coverage center and radius in `lib/modes.ts` must match `backend/app/config.py`.
