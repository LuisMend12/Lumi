import type { RouteMode } from "./api";

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

export function walkingMinutes(distanceM: number): number {
  return Math.max(1, Math.round(distanceM / WALKING_SPEED_M_PER_MIN));
}
