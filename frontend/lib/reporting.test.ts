import { describe, expect, it } from "vitest";
import { REPORT_OUTCOME_TEXT } from "./reporting";

// docs/team/api-contract.md: unverified and pending reports are never described as fact.
describe("REPORT_OUTCOME_TEXT", () => {
  it.each(["unverified", "pending"] as const)("says a %s report won't change routes", (outcome) => {
    expect(REPORT_OUTCOME_TEXT[outcome]).toContain("won't change routes");
  });
});
