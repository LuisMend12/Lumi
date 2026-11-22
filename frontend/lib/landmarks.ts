import type { LatLon } from "./api";

export interface Landmark {
  id: string;
  name: string;
  point: LatLon;
}

// Places inside the coverage area, each checked to route in every mode on the
// real BU graph (#8, #67). Keep the list short: it's a quick pick, not a search.
export const LANDMARKS: Landmark[] = [
  { id: "marsh-plaza", name: "Marsh Plaza", point: [42.3504, -71.106] },
  { id: "warren-towers", name: "Warren Towers", point: [42.349, -71.104] },
  { id: "kenmore", name: "Kenmore Square", point: [42.3489, -71.0951] },
  { id: "bu-bridge", name: "BU Bridge", point: [42.3537, -71.1105] },
  { id: "agganis", name: "Agganis Arena", point: [42.3523, -71.117] },
  { id: "packards", name: "Packard's Corner", point: [42.3518, -71.123] },
  { id: "st-marys", name: "St. Mary's St (Beacon St)", point: [42.348, -71.106] },
  { id: "audubon", name: "Audubon Circle", point: [42.3449, -71.1036] },
];
