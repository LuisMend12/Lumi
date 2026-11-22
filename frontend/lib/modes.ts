import type { Hazard, RouteMode, Verification } from "./api";

// Marsh Plaza, BU. Must match backend/app/config.py.
export const AREA_CENTER: [number, number] = [42.3504, -71.106];
export const AREA_RADIUS_M = 1500;

const WALKING_SPEED_M_PER_MIN = 80;

interface ModeStyle {
  label: string;
  color: string;
  dashArray?: string; // so modes differ by more than color
}

// Leaflet writes colors into SVG attributes, which can't read CSS variables,
// so map colors live here as hex values.
export const NAVY = "#102a43";

export const MODE_STYLES: Record<RouteMode, ModeStyle> = {
  shortest: { label: "Shortest", color: "#334e68" },
  safer: { label: "Safer", color: "#0284c7", dashArray: "1 10" },
  accessible: { label: "Accessible", color: "#7c3aed", dashArray: "12 8" },
};

// One line per mode, shown on every card so no mode reads as a safety promise (#66).
export const MODE_SUMMARIES: Record<RouteMode, string> = {
  shortest: "Most direct walk. May pass reported snow or ice.",
  safer: "Detours around reported snow, ice, and blocked sidewalks when it can.",
  accessible: "Avoids stairs and reported hazards.",
};

export const ACCESSIBLE_LIMITATION = "No curb-ramp or slope data yet. Check the route before relying on it.";

interface VerificationStyle {
  label: string;
  fill: string;
  fillOpacity: number;
}

// Each verification state has its own text label, not just a color, so an
// unverified or pending report is never shown as fact.
export const VERIFICATION_STYLES: Record<Verification, VerificationStyle> = {
  confirmed: { label: "Confirmed", fill: NAVY, fillOpacity: 1 },
  unverified: { label: "Unverified report", fill: "#ffffff", fillOpacity: 1 },
  pending: { label: "Under review", fill: "#9fb3c8", fillOpacity: 1 },
};

export function hazardLabel(hazard: Hazard): string {
  const what = hazard.blocked ? "Blocked" : capitalize(hazard.kind);
  const verification = VERIFICATION_STYLES[hazard.verification ?? "confirmed"].label;
  return `${what} · ${verification}`;
}

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function walkingMinutes(distanceM: number): number {
  return Math.max(1, Math.round(distanceM / WALKING_SPEED_M_PER_MIN));
}
