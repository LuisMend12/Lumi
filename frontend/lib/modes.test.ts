import { describe, expect, it } from "vitest";
import { ROUTE_MODES } from "./api";
import { MODE_STYLES, hazardLabel, walkingMinutes } from "./modes";

describe("hazardLabel", () => {
  it("names a blocked sidewalk and how sure we are", () => {
    expect(hazardLabel({ kind: "snow", severity: 1, blocked: true, verification: "unverified" })).toBe(
      "Blocked · Unverified report",
    );
  });

  it("names the hazard kind when it isn't blocked", () => {
    expect(hazardLabel({ kind: "ice", severity: 0.5, blocked: false, verification: "pending" })).toBe(
      "Ice · Under review",
    );
  });

  it("treats a hazard without a verification as confirmed (older backends don't send it)", () => {
    expect(hazardLabel({ kind: "snow", severity: 1, blocked: true })).toBe("Blocked · Confirmed");
  });
});

describe("walkingMinutes", () => {
  it("rounds at 80 m a minute", () => {
    expect(walkingMinutes(870.6)).toBe(11);
  });

  it("never says 0 minutes", () => {
    expect(walkingMinutes(10)).toBe(1);
  });
});

describe("MODE_STYLES", () => {
  it("tells modes apart by more than color", () => {
    const patterns = ROUTE_MODES.map((mode) => MODE_STYLES[mode].dashArray ?? "solid");
    expect(new Set(patterns).size).toBe(ROUTE_MODES.length);
  });
});
