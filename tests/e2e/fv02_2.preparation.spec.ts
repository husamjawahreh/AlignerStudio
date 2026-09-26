/**
 * FV-02.2 preparation job. One workflow, no screenshot suite.
 *
 * Requires the API at P8_API_URL (default http://127.0.0.1:8000) and the web app
 * at P8_WEB_URL (default http://127.0.0.1:5173). Uses the measured FV-02 STL when
 * that file is present. Does not invent a successful upload.
 */
import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEB = process.env.P8_WEB_URL ?? "http://127.0.0.1:5173";
const API = process.env.P8_API_URL ?? "http://127.0.0.1:8000";
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const REAL_STL = path.join(ROOT, "data/benchmark/real-case/upper.stl");
const REAL_SIZE = 8_557_034;

test("import a scan, run one preparation job, and show the technical state", async ({ page }) => {
  test.setTimeout(180_000);
  let health: Response | null = null;
  try {
    health = await fetch(`${API}/health`);
  } catch {
    health = null;
  }
  test.skip(
    health === null || !health.ok,
    `API is not reachable at ${API}. Live preparation was not verified.`,
  );
  test.skip(!fs.existsSync(REAL_STL), `Real STL is missing at ${REAL_STL}.`);
  const size = fs.statSync(REAL_STL).size;
  test.skip(
    size !== REAL_SIZE,
    `Real STL at ${REAL_STL} is ${size} bytes, not the measured ${REAL_SIZE}-byte file.`,
  );

  let webReady = false;
  try {
    const web = await fetch(WEB);
    webReady = web.ok;
  } catch {
    webReady = false;
  }
  test.skip(!webReady, `Web app is not reachable at ${WEB}. Live preparation was not verified.`);

  const started = Date.now();
  await page.goto(WEB);
  await page.getByLabel("Patient reference").fill("fv022");
  await expect(page.getByTestId("create-case-primary")).toBeEnabled();
  await page.getByTestId("create-case-primary").click();
  await expect(page.getByTestId("active-case-id")).toBeVisible({ timeout: 30_000 });
  await page.getByLabel("Upper Arch scan").setInputFiles(REAL_STL);
  await expect(page.getByText("Valid").first()).toBeVisible({ timeout: 60_000 });
  await page.getByText("File details").click();
  await expect(page.getByTestId("upper-intake-quality")).toContainText("vertices", { timeout: 60_000 });
  await page.getByRole("button", { name: "Rotate 90° Z" }).click();
  const job = page.getByTestId("upper-preparation-job");
  await expect(job).toBeVisible();
  await expect(job).toContainText(/orient (queued|running|completed)/);
  await expect(job).toContainText("completed", { timeout: 120_000 });
  await expect(page.getByTestId("upper-preparation-status")).toContainText("PREPARED");
  await expect(page.getByTestId("upper-preparation-status")).not.toContainText("clinically segmented");
  await expect(page.getByTestId("inspector-preparation")).toContainText("PREPARED");
  expect(page.getByRole("button", { name: "Rotate 90° Z" })).toBeEnabled();
  const elapsed = Date.now() - started;
  expect(elapsed).toBeGreaterThan(0);
});
