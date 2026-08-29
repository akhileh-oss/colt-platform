import { describe, expect, it } from "vitest";

import { VERSION } from "./index.js";

describe("@colt/api-client", () => {
  it("exposes a package version", () => {
    expect(VERSION).toBe("0.1.0");
  });
});
