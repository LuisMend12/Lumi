// Report and vote endpoints from docs/team/api-contract.md.
import { USE_MOCKS, type LatLon, type Verification } from "./api";

export type SegmentStatus = "open" | "blocked";
export type ReportOutcome = "status_changed" | "vote_recorded" | "unverified" | "pending";
export type VoteOutcome = "status_changed" | "vote_recorded" | "photo_required";

export interface ReportResult {
  report_id: string;
  segment_id: string;
  outcome: ReportOutcome;
  segment_status: SegmentStatus;
}

export interface VoteResult {
  outcome: VoteOutcome;
  segment_status: SegmentStatus;
}

export interface NearbySegment {
  segment_id: string;
  status: SegmentStatus;
  coordinates: LatLon[];
}

export interface Report {
  report_id: string;
  segment_id: string;
  location: LatLon;
  verification: Verification;
  reported_at: string;
  simulated: boolean;
}

export type ApiResult<T> = { ok: true; data: T } | { ok: false; message: string };

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const USER_ID_KEY = "lumi-user-id";
const OFFLINE_MESSAGE = "Can't reach the Lumi server. Check your connection and try again.";

const STATUS_MESSAGES: Record<number, string> = {
  403: "You need to be within 50 m of this sidewalk to answer.",
  404: "That sidewalk no longer exists on the map.",
  413: "The photo is too large. Try another photo.",
  415: "That file type isn't supported. Use a JPEG, PNG, or WebP photo.",
  422: "That spot is outside Lumi's coverage area.",
};

// Temporary stand-in for login (#14): a random ID kept in this browser.
export function userId(): string {
  try {
    const existing = localStorage.getItem(USER_ID_KEY);
    if (existing) return existing;
    const created = crypto.randomUUID();
    localStorage.setItem(USER_ID_KEY, created);
    return created;
  } catch {
    return "anonymous";
  }
}

export async function submitReport(location: LatLon, photo: Blob): Promise<ApiResult<ReportResult>> {
  if (USE_MOCKS) return (await import("./mocks")).mockSubmitReport(location);
  const form = new FormData();
  form.append("lat", String(location[0]));
  form.append("lon", String(location[1]));
  form.append("photo", photo, "report.jpg");
  return request<ReportResult>("/reports", { method: "POST", body: form });
}

export async function voteOnSegment(segmentId: string, blocked: boolean, location: LatLon): Promise<ApiResult<VoteResult>> {
  if (USE_MOCKS) return (await import("./mocks")).mockVote();
  return request<VoteResult>(`/segments/${encodeURIComponent(segmentId)}/votes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ blocked, lat: location[0], lon: location[1] }),
  });
}

export async function fetchNearby(location: LatLon): Promise<ApiResult<NearbySegment[]>> {
  if (USE_MOCKS) return (await import("./mocks")).mockNearby(location);
  return request<NearbySegment[]>(`/segments/nearby?lat=${location[0]}&lon=${location[1]}`, {});
}

export async function fetchReports(): Promise<ApiResult<Report[]>> {
  if (USE_MOCKS) return (await import("./mocks")).mockReports();
  return request<Report[]>("/reports", {});
}

async function request<T>(path: string, init: RequestInit): Promise<ApiResult<T>> {
  const headers = { ...(init.headers as Record<string, string> | undefined), "X-User-Id": userId() };
  try {
    const response = await fetch(`${API_URL}${path}`, { ...init, headers });
    const body: unknown = await response.json().catch(() => null);
    if (response.ok) return { ok: true, data: body as T };
    return { ok: false, message: errorMessage(response.status, body) };
  } catch {
    return { ok: false, message: OFFLINE_MESSAGE };
  }
}

function errorMessage(status: number, body: unknown): string {
  if (STATUS_MESSAGES[status]) return STATUS_MESSAGES[status];
  const detail = (body as { detail?: unknown } | null)?.detail;
  return typeof detail === "string" ? detail : "Something went wrong. Please try again.";
}
