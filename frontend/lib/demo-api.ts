// Demo-mode endpoints (#38, docs/team/api-contract.md "Demo mode"). They exist
// only when the backend runs with LUMI_DEMO_MODE=1; everything they create is
// simulated and shown with a "Simulated" badge.
import { USE_MOCKS, type LatLon } from "./api";
import { request, type ApiResult, type ReportResult, type SegmentStatus, type VoteOutcome } from "./reports-api";

export interface DemoVotesResult {
  votes_cast: number;
  outcome: VoteOutcome;
  segment_status: SegmentStatus;
}

const JSON_POST = { method: "POST", headers: { "Content-Type": "application/json" } } as const;

export async function isDemoMode(): Promise<boolean> {
  if (USE_MOCKS) return true;
  const result = await request<{ demo_mode: boolean }>("/demo/status", {});
  return result.ok && result.data.demo_mode === true;
}

export async function nearestSegment(point: LatLon): Promise<ApiResult<{ segment_id: string }>> {
  if (USE_MOCKS) return (await import("./mocks")).mockNearestSegment(point);
  return request(`/demo/segments/nearest?lat=${point[0]}&lon=${point[1]}`, {});
}

export async function simulateBlock(segmentId: string): Promise<ApiResult<ReportResult>> {
  if (USE_MOCKS) return (await import("./mocks")).mockDemoBlock(segmentId);
  return request(`/demo/segments/${encodeURIComponent(segmentId)}/block`, { method: "POST" });
}

export async function simulateVotes(segmentId: string, blocked: boolean, voters = 4): Promise<ApiResult<DemoVotesResult>> {
  if (USE_MOCKS) return (await import("./mocks")).mockDemoVotes(voters);
  return request(`/demo/segments/${encodeURIComponent(segmentId)}/votes`, {
    ...JSON_POST,
    body: JSON.stringify({ blocked, voters }),
  });
}

export async function resetDemo(): Promise<ApiResult<{ removed: number }>> {
  if (USE_MOCKS) return (await import("./mocks")).mockDemoReset();
  return request("/demo/reset", { method: "POST" });
}

// A point halfway between two consecutive route points lies on a segment the
// route really uses, unlike a route vertex, which is an intersection.
export function pointHalfwayAlong(coordinates: LatLon[]): LatLon | null {
  if (coordinates.length < 2) return null;
  const i = Math.floor((coordinates.length - 1) / 2);
  const [a, b] = [coordinates[i], coordinates[i + 1]];
  return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
}
