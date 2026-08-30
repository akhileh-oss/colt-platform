import { describe, expect, it } from "vitest";

import { isColtErrorResponse } from "./errors";

describe("isColtErrorResponse", () => {
  it("recognises a well-formed envelope", () => {
    expect(
      isColtErrorResponse({
        error: {
          code: "NOT_FOUND",
          message: "Lead was not found.",
          request_id: "req_1",
          details: null,
        },
      }),
    ).toBe(true);
  });

  it("rejects a plain object", () => {
    expect(isColtErrorResponse({ message: "oops" })).toBe(false);
  });

  it("rejects null and primitives", () => {
    expect(isColtErrorResponse(null)).toBe(false);
    expect(isColtErrorResponse("error")).toBe(false);
    expect(isColtErrorResponse(42)).toBe(false);
  });

  it("rejects an error field missing a code", () => {
    expect(isColtErrorResponse({ error: { message: "oops" } })).toBe(false);
  });
});
