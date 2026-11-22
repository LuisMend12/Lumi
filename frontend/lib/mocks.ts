// Sample responses shaped like docs/team/api-contract.md, for building the UI
// before the backend sends the new fields. Only used when
// NEXT_PUBLIC_USE_MOCKS=true, and the page labels everything as mock data.
import type { Hazard, LatLon, RouteMode, RouteOutcome } from "./api";
import type {
  ApiResult,
  NearbySegment,
  Report,
  ReportOutcome,
  ReportResult,
  VoteOutcome,
  VoteResult,
} from "./reports-api";

const MODE_DESCRIPTIONS: Record<RouteMode, string> = {
  shortest: "Shortest: the most direct walk. Skips sidewalks reported fully blocked, but may pass reported snow or ice.",
  safer: "Safer: detours around reported snow, ice, and obstructions when a reasonable alternative exists. Not a guarantee that the route is safe.",
  accessible: "Accessible: skips blocked sidewalks and avoids reported hazards. Curb ramp and slope data is not included yet.",
};

const SNAP_OFFSET = 0.0002; // ~20 m, so the dashed snap leg is visible
const TOO_CLOSE_M = 30;
const DETOUR_OFFSET = 0.0012; // how far Safer / Accessible bend away from the hazards

export function mockRoute(start: LatLon, end: LatLon, mode: RouteMode): RouteOutcome {
  if (distanceM(start, end) < TOO_CLOSE_M) {
    return { status: "error", message: "Start and destination are too close." };
  }
  const snappedStart: LatLon = [start[0] + SNAP_OFFSET, start[1] - SNAP_OFFSET];
  const snappedEnd: LatLon = [end[0] - SNAP_OFFSET, end[1] + SNAP_OFFSET];
  const mid = midpoint(snappedStart, snappedEnd);
  const isDetour = mode !== "shortest";
  const bend: LatLon = isDetour ? [mid[0] - DETOUR_OFFSET, mid[1] - DETOUR_OFFSET] : mid;
  const coordinates = [snappedStart, bend, snappedEnd];

  return {
    status: "ok",
    route: {
      mode,
      mode_description: MODE_DESCRIPTIONS[mode],
      distance_m: pathLength(coordinates),
      coordinates,
      snapped_start: snappedStart,
      snapped_end: snappedEnd,
      hazards: isDetour ? [] : hazardsAlong(snappedStart, snappedEnd),
    },
  };
}

function hazardsAlong(a: LatLon, b: LatLon): Hazard[] {
  const at = (t: number): LatLon => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
  return [
    { segment_id: "mock-1", location: at(0.3), kind: "ice", severity: 0.6, blocked: false, verification: "confirmed" },
    { segment_id: "mock-2", location: at(0.55), kind: "snow", severity: 0.4, blocked: false, verification: "unverified" },
    { segment_id: "mock-3", location: at(0.8), kind: "obstruction", severity: 0.8, blocked: false, verification: "pending" },
  ];
}

// --- Reports and votes: each call cycles to the next outcome, so every
// message can be seen and screenshotted without the backend.

const REPORT_OUTCOMES: ReportOutcome[] = ["status_changed", "unverified", "pending", "vote_recorded"];
const VOTE_OUTCOMES: VoteOutcome[] = ["vote_recorded", "status_changed", "photo_required"];
const NEARBY_OFFSET = 0.0002; // ~20 m east of the user

let reportCount = 0;
let voteCount = 0;
let mockReportList: Report[] = [
  {
    report_id: "r_sim1",
    segment_id: "mock-sim-1",
    location: [42.3512, -71.1035],
    verification: "confirmed",
    reported_at: "2026-11-21T18:04:00Z",
    simulated: true,
  },
];

export function mockSubmitReport(location: LatLon): ApiResult<ReportResult> {
  const outcome = REPORT_OUTCOMES[reportCount++ % REPORT_OUTCOMES.length];
  const report: Report = {
    report_id: `r_mock${reportCount}`,
    segment_id: `mock-seg-${reportCount}`,
    location,
    verification: outcome === "unverified" ? "unverified" : outcome === "pending" ? "pending" : "confirmed",
    reported_at: new Date().toISOString(),
    simulated: true,
  };
  mockReportList = [...mockReportList, report];
  return {
    ok: true,
    data: { report_id: report.report_id, segment_id: report.segment_id, outcome, segment_status: "blocked" },
  };
}

export function mockVote(): ApiResult<VoteResult> {
  const outcome = VOTE_OUTCOMES[voteCount++ % VOTE_OUTCOMES.length];
  return { ok: true, data: { outcome, segment_status: outcome === "status_changed" ? "open" : "blocked" } };
}

export function mockNearby(location: LatLon): ApiResult<NearbySegment[]> {
  const [lat, lon] = location;
  return {
    ok: true,
    data: [
      {
        segment_id: "mock-nearby-1",
        status: "blocked",
        coordinates: [
          [lat, lon + NEARBY_OFFSET],
          [lat, lon + NEARBY_OFFSET * 3],
        ],
      },
    ],
  };
}

export function mockReports(): ApiResult<Report[]> {
  return { ok: true, data: mockReportList };
}

function midpoint(a: LatLon, b: LatLon): LatLon {
  return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
}

function pathLength(points: LatLon[]): number {
  return points.slice(1).reduce((sum, point, i) => sum + distanceM(points[i], point), 0);
}

function distanceM(a: LatLon, b: LatLon): number {
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const dLat = toRad(b[0] - a[0]);
  const dLon = toRad(b[1] - a[1]);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a[0])) * Math.cos(toRad(b[0])) * Math.sin(dLon / 2) ** 2;
  return 2 * 6_371_000 * Math.asin(Math.sqrt(h));
}
