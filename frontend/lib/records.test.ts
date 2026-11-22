import { describe, expect, it } from "vitest";
import { withoutKey } from "./records";

describe("withoutKey", () => {
  it("drops just that key and leaves the original untouched", () => {
    const messages = { a: 1, b: 2 };

    expect(withoutKey(messages, "a")).toEqual({ b: 2 });
    expect(messages).toEqual({ a: 1, b: 2 });
  });

  it("returns an equal copy when the key isn't there", () => {
    const messages = { a: 1 };

    const result = withoutKey(messages, "z");

    expect(result).toEqual({ a: 1 });
    expect(result).not.toBe(messages);
  });
});
