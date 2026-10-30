// Runtime validation coverage for shared date and status formatting.
import { describe, expect, it } from "vitest";
import { formatIST, istInputToISO, statusLabel } from "./format";

describe("shared format helpers", () => {
  it("formats status codes as readable labels", () => {
    expect(statusLabel("PENDING_REVIEW")).toBe("PENDING REVIEW");
  });

  it("converts an IST input to a UTC timestamp", () => {
    expect(istInputToISO("2026-03-20T14:30")).toBe("2026-03-20T09:00:00.000Z");
  });

  it("returns an explicit fallback for a missing timestamp", () => {
    expect(formatIST(null)).toBe("Not provided");
  });
});
