/**
 * Optional Playwright smoke — enabled only when P8_RUN_PLAYWRIGHT=1.
 * Requires a running API + web preview; does not invent clinical evidence.
 */
import { test, expect } from "@playwright/test";

const WEB = process.env.P8_WEB_URL ?? "http://127.0.0.1:5173";
const API = process.env.P8_API_URL ?? "http://127.0.0.1:8000";

test.describe("P8 optional smoke", () => {
  test("API health is reachable", async ({ request }) => {
    const response = await request.get(`${API}/health`);
    expect(response.ok()).toBeTruthy();
    expect(await response.json()).toEqual({ status: "ok" });
  });

  test("engineering demo loads fixture labeling in the browser", async ({ page }) => {
    test.skip(!process.env.P8_RUN_PLAYWRIGHT, "Set P8_RUN_PLAYWRIGHT=1 with live web+API");
    await page.goto(WEB);
    await page.getByRole("button", { name: "Load engineering demo" }).click();
    await expect(page.getByText(/FIXTURE|engineering-fixture-demo/i).first()).toBeVisible({
      timeout: 60_000,
    });
  });
});
