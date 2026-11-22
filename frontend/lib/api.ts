export type RouteMode = "shortest" | "safer" | "accessible";

export const ROUTE_MODES: RouteMode[] = ["shortest", "safer", "accessible"];

export type LatLon = [number, number];

export type Verification = "confirmed" | "unverified" | "pending";

// Fields marked optional are new in docs/team/api-contract.md; the current
// backend doesn't send them yet, so the UI must work without them.
export interface Hazard {
  kind: string;
  severity: number;
  blocked: boolean;
  segment_id?: string;
  location?: LatLon;
  verification?: Verification;
}

export interface Route {
  mode: RouteMode;
  mode_description: string;
  distance_m: number;
  coordinates: LatLon[];
  hazards: Hazard[];
  snapped_start?: LatLon;
  snapped_end?: LatLon;
}

export type RouteOutcome =
  | { status: "ok"; route: Route }
  // `offline`: the request never reached the server (no answer), so the route may still be fine.
  | { status: "error"; message: string; offline?: true };

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

// Serve sample data in the API contract's shape instead of calling the backend.
export const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS === "true";

export async function fetchRoute(start: LatLon, end: LatLon, mode: RouteMode): Promise<RouteOutcome> {
  if (USE_MOCKS) {
    const { mockRoute } = await import("./mocks");
    return mockRoute(start, end, mode);
  }
  const params = new URLSearchParams({
    start_lat: String(start[0]),
    start_lon: String(start[1]),
    end_lat: String(end[0]),
    end_lon: String(end[1]),
    mode,
  });
  try {
    const response = await fetch(`${API_URL}/route?${params}`);
    const body: unknown = await response.json();
    if (response.ok) return { status: "ok", route: body as Route };
    return { status: "error", message: errorMessage(response.status, body) };
  } catch {
    return { status: "error", message: "Can't reach the Lumi server. Is the backend running?", offline: true };
  }
}

function errorMessage(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown })?.detail;
  if (typeof detail === "string") return detail;
  if (status === 404) return "No route avoids the blocked sidewalks.";
  return "Something went wrong getting this route.";
}
