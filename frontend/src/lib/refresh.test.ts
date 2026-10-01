import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";
import { apiRequest } from "./api";

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  sessionStorage.clear();
  vi.useRealTimers();
});
afterAll(() => server.close());

describe("refresh retries", () => {
  it("shares one refresh for concurrent 401s and retries each request once", async () => {
    vi.useFakeTimers();
    let refreshCalls = 0;
    server.use(
      http.get("/api/v1/protected", ({ request }) =>
        request.headers.get("authorization") === "Bearer renewed-access"
          ? HttpResponse.json({ ok: true })
          : new HttpResponse(null, { status: 401 }),
      ),
      http.post("/api/v1/auth/token/refresh/", async () => {
        refreshCalls += 1;
        await new Promise((resolve) => setTimeout(resolve, 10));
        return HttpResponse.json({ access: "renewed-access", refresh: "rotated-refresh" });
      }),
    );
    sessionStorage.setItem("deverp.refresh", "refresh-token");

    const requests = Promise.all([
      apiRequest<{ ok: boolean }>("/protected", {}, "expired-access"),
      apiRequest<{ ok: boolean }>("/protected", {}, "expired-access"),
    ]);
    await vi.advanceTimersByTimeAsync(10);

    await expect(requests).resolves.toEqual([{ ok: true }, { ok: true }]);
    expect(refreshCalls).toBe(1);
    expect(sessionStorage.getItem("deverp.access")).toBe("renewed-access");
    expect(sessionStorage.getItem("deverp.refresh")).toBe("rotated-refresh");
  });

  it("expires the session after the retry also returns 401", async () => {
    let refreshCalls = 0;
    const expired = vi.fn();
    window.addEventListener("deverp:session-expired", expired);
    server.use(
      http.get("/api/v1/protected", () => new HttpResponse(null, { status: 401 })),
      http.post("/api/v1/auth/token/refresh/", () => {
        refreshCalls += 1;
        return HttpResponse.json({ access: "renewed-access" });
      }),
    );
    sessionStorage.setItem("deverp.refresh", "refresh-token");
    sessionStorage.setItem("deverp.user", "{}");

    await expect(apiRequest("/protected", {}, "expired-access")).rejects.toMatchObject({
      status: 401,
    });
    window.removeEventListener("deverp:session-expired", expired);

    expect(refreshCalls).toBe(1);
    expect(expired).toHaveBeenCalledTimes(1);
    expect(sessionStorage.length).toBe(0);
  });
});
