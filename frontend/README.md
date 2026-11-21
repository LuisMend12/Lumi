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

| Variable (in `.env.local`) | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://127.0.0.1:8000` | Where the backend runs |

`NEXT_PUBLIC_*` values are bundled into the browser code, so never put secrets in them.

## Layout

```
app/page.tsx             page state: clicked points, fetched routes, selected mode, mode cards
app/globals.css          winter palette (CSS variables)
components/RouteMap.tsx  Leaflet map, coverage circle, route lines (browser-only, loaded with ssr: false)
lib/api.ts               typed calls to GET /route, readable error messages
lib/modes.ts             coverage area, per-mode colors and dash patterns, walking time
```

The coverage center and radius in `lib/modes.ts` must match `backend/app/config.py`.
