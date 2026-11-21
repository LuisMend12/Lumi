export type RouteMode = "shortest" | "safer" | "accessible";

export const ROUTE_MODES: RouteMode[] = ["shortest", "safer", "accessible"];

export type LatLon = [number, number];

export interface Hazard {
  kind: string;
  severity: number;
  blocked: boolean;
}

export interface Route {
  mode: RouteMode;
  mode_description: string;
  distance_m: number;
  coordinates: LatLon[];
  hazards: Hazard[];
}

export type RouteOutcome =
  | { status: "ok"; route: Route }
  | { status: "error"; message: string };

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export async function fetchRoute(start: LatLon, end: LatLon, mode: RouteMode): Promise<RouteOutcome> {
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
    return { status: "error", message: "Can't reach the Lumi server. Is the backend running?" };
  }
}

function errorMessage(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown })?.detail;
  if (typeof detail === "string") return detail;
  if (status === 404) return "No route avoids the blocked sidewalks.";
  return "Something went wrong getting this route.";
}
