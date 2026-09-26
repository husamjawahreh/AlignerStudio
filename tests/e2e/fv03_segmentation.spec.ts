/**
 * FV-03 segmentation boundary. One workflow, no screenshot suite.
 *
 * Uses the measured FV-02 STL. A blocked runtime is a valid result.
 * The test does not invent a completed segmentation.
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

test("accept a prepared scan and show segmentation provenance or the runtime blocker", async ({
  page,
}) => {
  test.setTimeout(240_000);
  let health: Response | null = null;
  try {
    health = await fetch(`${API}/health`);
  } catch {
    health = null;
  }
  test.skip(health === null || !health.ok, `API is not reachable at ${API}.`);
  test.skip(!fs.existsSync(REAL_STL), `Real STL is missing at ${REAL_STL}.`);
  const size = fs.statSync(REAL_STL).size;
  test.skip(size !== REAL_SIZE, `Real STL is ${size} bytes, not ${REAL_SIZE}.`);
  let webReady = false;
  try {
    webReady = (await fetch(WEB)).ok;
  } catch {
    webReady = false;
  }
  test.skip(!webReady, `Web app is not reachable at ${WEB}.`);

  const started = Date.now();
  await page.goto(WEB);
  await page.getByLabel("Patient reference").fill("fv03");
  await expect(page.getByTestId("create-case-primary")).toBeEnabled();
  await page.getByTestId("create-case-primary").click();
  await expect(page.getByTestId("active-case-id")).toBeVisible({ timeout: 30_000 });
  await page.getByLabel("Upper Arch scan").setInputFiles(REAL_STL);
  await expect(page.getByText("Valid").first()).toBeVisible({ timeout: 60_000 });
  await page.getByText("File details").click();
  await expect(page.getByTestId("upper-intake-quality")).toContainText("vertices", { timeout: 60_000 });
  await page.getByRole("button", { name: "Rotate 90° Z" }).click();
  await expect(page.getByTestId("upper-preparation-job")).toContainText("completed", { timeout: 120_000 });
  await page.getByRole("button", { name: "Accept for segmentation" }).click();
  await expect(page.getByTestId("upper-preparation-status")).toContainText(
    /READY_FOR_SEGMENTATION|READY_WITH_WARNINGS/,
    { timeout: 60_000 },
  );
  await page.getByRole("button", { name: "Start segmentation" }).click();
  const job = page.getByTestId("upper-segmentation-job");
  await expect(job).toBeVisible();
  await expect(job).toContainText(/queued|running|completed|failed/);
  await expect(job).toContainText(/completed|blocked|DRIVER_UNAVAILABLE|ENVIRONMENT_BLOCKED|AVAILABLE/, {
    timeout: 120_000,
  });
  const identity = page.getByTestId("upper-segmentation-identity");
  await expect(identity).toContainText("NOT_ESTABLISHED");
  await expect(identity).toContainText("not established");
  await expect(page.getByTestId("upper-segmentation-review")).toBeVisible();
  await expect(page.getByTestId("inspector-segmentation-identity")).toContainText("NOT_ESTABLISHED");
  await expect(page.getByTestId("upper-segmentation-review")).not.toContainText("FDI 11");
  expect(Date.now() - started).toBeGreaterThan(0);
});
