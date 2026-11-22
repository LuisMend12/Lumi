import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchRoute, type LatLon } from "./api";

const START: LatLon = [42.35, -71.108];
const END: LatLon = [42.35, -71.1056];

function respond(status: number, body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchRoute", () => {
  it("sends the start, end and mode as query parameters", async () => {
    const fetchMock = respond(200, { mode: "safer" });

    await fetchRoute(START, END, "safer");

    const url = new URL(fetchMock.mock.calls[0][0]);
    expect(url.pathname).toBe("/route");
    expect(Object.fromEntries(url.searchParams)).toEqual({
      start_lat: "42.35",
      start_lon: "-71.108",
      end_lat: "42.35",
      end_lon: "-71.1056",
      mode: "safer",
    });
  });

  it("returns the route on success", async () => {
    const route = { mode: "shortest", mode_description: "", distance_m: 870.6, coordinates: [], hazards: [] };
    respond(200, route);

    expect(await fetchRoute(START, END, "shortest")).toEqual({ status: "ok", route });
  });

  it("shows the server's own message when it sends one", async () => {
    respond(422, { detail: "This spot is outside Lumi's coverage area." });

    expect(await fetchRoute(START, END, "shortest")).toEqual({
      status: "error",
      message: "This spot is outside Lumi's coverage area.",
    });
  });

  it("explains a 404 without a message as no route around blocked sidewalks", async () => {
    respond(404, {});

    expect(await fetchRoute(START, END, "shortest")).toEqual({
      status: "error",
      message: "No route avoids the blocked sidewalks.",
    });
  });

  it("doesn't mark a server's answer as offline", async () => {
    respond(404, {});

    const outcome = await fetchRoute(START, END, "shortest");
    expect(outcome.status === "error" && outcome.offline).toBeFalsy();
  });

  it("falls back to a generic message for other errors", async () => {
    respond(500, { detail: [{ msg: "not a string" }] });

    expect(await fetchRoute(START, END, "shortest")).toEqual({
      status: "error",
      message: "Something went wrong getting this route.",
    });
  });

  it("treats a non-JSON error page (a proxy's 502) as a server error, not as unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>502 Bad Gateway</html>", { status: 502 })));

    expect(await fetchRoute(START, END, "shortest")).toEqual({
      status: "error",
      message: "Something went wrong getting this route.",
    });
  });

  it("says the server can't be reached when the request itself fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    expect(await fetchRoute(START, END, "shortest")).toEqual({
      status: "error",
      message: "Can't reach the Lumi server. Is the backend running?",
      offline: true,
    });
  });
});
