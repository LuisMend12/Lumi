import type { Hazard, RouteMode, Verification } from "./api";

// Marsh Plaza, BU. Must match backend/app/config.py.
export const AREA_CENTER: [number, number] = [42.3504, -71.106];
export const AREA_RADIUS_M = 1500;

const WALKING_SPEED_M_PER_MIN = 80;

interface ModeStyle {
  label: string;
  color: string; // the mode's own colour: its map line, and its chyron when chosen
  ink: string; // text on a chyron flooded with `color`
  casing: { color: string; opacity: number }; // underlay that keeps the line legible on the pale basemap
  dashArray?: string; // so modes differ by more than color
}

// Leaflet writes colors into SVG attributes, which can't read CSS variables,
// so map colors live here as hex values. Storm Center palette (#68).
export const NAVY = "#0b2545";
export const STORM = "#1d4e89";
export const SKY = "#8ecae6";
export const AMBER = "#ffb703";
export const WHITE = "#ffffff";

export const MODE_STYLES: Record<RouteMode, ModeStyle> = {
  shortest: { label: "Shortest", color: SKY, ink: NAVY, casing: { color: NAVY, opacity: 0.32 } },
  safer: { label: "Safer", color: STORM, ink: WHITE, dashArray: "1 10", casing: { color: WHITE, opacity: 1 } },
  accessible: { label: "Accessible", color: NAVY, ink: WHITE, dashArray: "12 8", casing: { color: WHITE, opacity: 1 } },
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
  stroke: string;
  dashArray?: string;
}

// Verification is a mark in a fixed cell: filled confirmed, hollow unverified,
// dotted under review (#68). Each state also has its own text label, so an
// unverified or pending report is never shown as fact.
export const VERIFICATION_STYLES: Record<Verification, VerificationStyle> = {
  confirmed: { label: "Confirmed", fill: NAVY, fillOpacity: 1, stroke: WHITE },
  unverified: { label: "Unverified report", fill: WHITE, fillOpacity: 1, stroke: AMBER },
  pending: { label: "Under review", fill: WHITE, fillOpacity: 1, stroke: NAVY, dashArray: "1 4" },
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
