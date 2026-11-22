import { describe, expect, it } from "vitest";
import { createRequestTracker } from "./latest";

describe("createRequestTracker", () => {
  it("keeps only the newest request current", () => {
    const tracker = createRequestTracker();
    const first = tracker.begin();
    expect(first()).toBe(true);

    const second = tracker.begin();
    expect(first()).toBe(false);
    expect(second()).toBe(true);
  });

  it("makes the request in flight stale on cancel", () => {
    const tracker = createRequestTracker();
    const request = tracker.begin();

    tracker.cancel();

    expect(request()).toBe(false);
  });

  it("drops a slow lookup that finishes after a newer choice", async () => {
    const tracker = createRequestTracker();
    const applied: string[] = [];
    let finishSlow: (value: string) => void = () => {};
    const slow = new Promise<string>((resolve) => (finishSlow = resolve));

    async function choose(lookup: Promise<string>) {
      const isCurrent = tracker.begin();
      const value = await lookup;
      if (isCurrent()) applied.push(value);
    }

    const pending = choose(slow); // My location: waits for GPS
    await choose(Promise.resolve("Warren Towers")); // then a landmark, right away
    finishSlow("GPS position");
    await pending;

    expect(applied).toEqual(["Warren Towers"]);
  });
});
