import { describe, expect, it } from "vitest";
import { ROUTE_CONTRACT, ROUTES } from "./route-contract";

describe("ROUTE_CONTRACT", () => {
  it("provides unique paths without the legacy admin route", () => {
    expect(new Set(ROUTES).size).toBe(ROUTES.length);
    expect(ROUTES).not.toContain("/admin");
    expect(ROUTE_CONTRACT.ACCESS).toBe("/access");
    expect(ROUTE_CONTRACT.SETTINGS).toBe("/settings");
  });
});
