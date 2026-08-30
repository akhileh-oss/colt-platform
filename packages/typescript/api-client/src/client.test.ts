import { describe, expect, it, vi } from "vitest";

import { createColtClient } from "./client";

describe("createColtClient", () => {
  it("calls a real route with a typed response", async () => {
    const fetchMock = vi.fn(
      async (_request: Request) =>
        new Response(JSON.stringify({ status: "alive" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const client = createColtClient({ baseUrl: "http://localhost:8000" });
    const { data, error } = await client.GET("/live");

    expect(error).toBeUndefined();
    expect(data).toEqual({ status: "alive" });
    const [request] = fetchMock.mock.calls[0]!;
    expect(request.url).toBe("http://localhost:8000/live");
  });

  it("attaches the request ID header when a provider is given", async () => {
    const fetchMock = vi.fn(
      async (_request: Request) =>
        new Response(JSON.stringify({ status: "alive" }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const client = createColtClient({
      baseUrl: "http://localhost:8000",
      getRequestId: () => "req_test_123",
    });
    await client.GET("/live");

    const [request] = fetchMock.mock.calls[0]!;
    expect(request.headers.get("X-Request-ID")).toBe("req_test_123");
  });

  it("omits the header when the provider returns undefined", async () => {
    const fetchMock = vi.fn(
      async (_request: Request) =>
        new Response(JSON.stringify({ status: "alive" }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const client = createColtClient({
      baseUrl: "http://localhost:8000",
      getRequestId: () => undefined,
    });
    await client.GET("/live");

    const [request] = fetchMock.mock.calls[0]!;
    expect(request.headers.has("X-Request-ID")).toBe(false);
  });
});
