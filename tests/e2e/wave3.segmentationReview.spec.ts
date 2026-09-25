/**
 * Wave 3 browser QA.
 *
 * UI evidence only. Mocked pipeline responses are not clinical segmentation
 * evidence. Blocked and fixture states are labeled as such.
 *
 * Requires the web app at P8_WEB_URL (default http://127.0.0.1:5173).
 */
import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEB = process.env.P8_WEB_URL ?? "http://127.0.0.1:5173";
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const EVIDENCE_DIR = path.join(ROOT, ".research/tmp/wave3_browser_qa");

const VIEWPORTS = [
  { width: 1366, height: 768, name: "1366x768" },
  { width: 1600, height: 1000, name: "1600x1000" },
] as const;

function triangle(arch: "upper" | "lower") {
  return {
    instance_id: arch === "upper" ? 0 : 1,
    fdi_number: arch === "upper" ? 11 : 31,
    tooth_ref: `${arch}:instance:0`,
    arch,
    vertices: [
      [0, 0, 0],
      [1, 0, 0],
      [0, 1, 0],
    ],
    faces: [[0, 1, 2]],
    centroid: [0, 0, 0],
    confidence: 0.4,
    provenance: "fixture",
    fixture: true,
    experimental: true,
    planning_mode: "semantic_only_experimental",
    identification_status: "uncertain",
  };
}

async function shot(page: Page, name: string): Promise<void> {
  fs.mkdirSync(EVIDENCE_DIR, { recursive: true });
  await page.screenshot({ path: path.join(EVIDENCE_DIR, `${name}.png`), fullPage: false });
}

async function installApi(page: Page, mode: "blocked" | "fixture"): Promise<void> {
  await page.route("**/cases**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    if (method === "POST" && /\/cases$/.test(url)) {
      await route.fulfill({
        json: {
          id: "wave3-case",
          patient_reference: "wave3-review",
          status: "created",
          meshes: [],
          created_at: "2026-09-26T00:00:00Z",
        },
      });
      return;
    }
    if (method === "POST" && url.includes("/uploads") && !url.includes("validate")) {
      const arch = url.includes("arch=lower") ? "lower" : "upper";
      await route.fulfill({
        json: {
          id: "wave3-case",
          patient_reference: "wave3-review",
          status: "mesh_validated",
          meshes: [
            {
              arch,
              file_path: `/tmp/${arch}.stl`,
              original_filename: `${arch}.stl`,
              uploaded_at: "2026-09-26T00:00:00Z",
            },
          ],
          created_at: "2026-09-26T00:00:00Z",
        },
      });
      return;
    }
    if (method === "POST" && url.includes("/validate")) {
      await route.fulfill({
        json: { is_valid: true, triangle_count: 12, is_watertight: true, errors: [] },
      });
      return;
    }
    if (method === "POST" && url.includes("/pipeline/")) {
      const arch = url.includes("/lower") ? "lower" : "upper";
      if (mode === "blocked") {
        await route.fulfill({
          json: {
            state: "blocked_by_environment",
            segmentation_truth_state: "blocked_by_environment",
            source_kind: "uploaded_real_case",
            runtime_blocker: "No NVIDIA driver, torch, or pointops on this host.",
            segmentation_runtime_ms: null,
            total_runtime_ms: 1,
            tooth_instance_count: 0,
            identification_confidence: null,
            identified_teeth: 0,
            uncertain_teeth: 0,
            unidentified_teeth: 0,
            validation_findings: [],
            failures: ["Live ToothInstanceNet inference did not run."],
            arch_analysis_available: false,
            notes: [],
            provenance: "real",
            fixture: false,
            tooth_instances: [],
          },
        });
        return;
      }
      await route.fulfill({
        json: {
          state: "identification_incomplete",
          source_kind: "validated_real_case",
          segmentation_runtime_ms: 4,
          total_runtime_ms: 8,
          tooth_instance_count: 1,
          identification_confidence: 0.4,
          identified_teeth: 0,
          uncertain_teeth: 1,
          unidentified_teeth: 1,
          validation_findings: [],
          failures: [],
          arch_analysis_available: false,
          notes: ["fixture presentation"],
          provenance: "fixture",
          fixture: true,
          experimental: true,
          tooth_instances: [triangle(arch)],
        },
      });
      return;
    }
    await route.fulfill({ status: 404, body: "unmocked" });
  });
}

async function assertNoPageOverflow(page: Page): Promise<void> {
  const metrics = await page.evaluate(() => ({
    scrollHeight: document.documentElement.scrollHeight,
    clientHeight: document.documentElement.clientHeight,
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(metrics.scrollHeight).toBeLessThanOrEqual(metrics.clientHeight + 4);
  expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.clientWidth + 4);
}

test.describe("Wave 3 segmentation review workspace", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      try {
        sessionStorage.clear();
      } catch {
        /* ignore */
      }
    });
  });

  for (const viewport of VIEWPORTS) {
    test(`launch and blocked review at ${viewport.name}`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await installApi(page, "blocked");
      await page.goto(WEB);
      await expect(page.getByTestId("primary-status")).toHaveCount(1);
      await expect(page.locator("[data-status-surface='primary']")).toHaveCount(1);
      await expect(page.getByTestId("case-status-compact")).toHaveCount(0);
      await shot(page, `${viewport.name}_01_launch`);
      await assertNoPageOverflow(page);

      const header = await page.locator(".cad-header").boundingBox();
      const shell = await page.locator(".cad-shell").boundingBox();
      expect(header).not.toBeNull();
      expect(shell).not.toBeNull();
      expect((header?.y ?? 0) + (header?.height ?? 0)).toBeLessThanOrEqual(shell?.height ?? 0);

      await page.locator("#patient-reference").fill("wave3-review");
      await page.getByTestId("create-case-primary").click();
      await expect(page.getByTestId("case-intake-panel")).toHaveAttribute("data-case-state", "active");
      await shot(page, `${viewport.name}_02_case_intake`);

      await page.locator("#upper-stl").setInputFiles({
        name: "upper.stl",
        mimeType: "model/stl",
        buffer: Buffer.from("upper"),
      });
      await page.locator("#lower-stl").setInputFiles({
        name: "lower.stl",
        mimeType: "model/stl",
        buffer: Buffer.from("lower"),
      });
      await page.getByRole("button", { name: "Review segmentation" }).click();
      await expect(page.getByTestId("segmentation-review-strip")).toHaveAttribute(
        "data-segmentation-kind",
        "blocked_by_environment",
      );
      await expect(page.getByTestId("analysis-tooth-count")).toHaveText("Not available");
      await expect(page.getByTestId("segmentation-runtime-blocker")).toContainText("pointops");
      await expect(page.getByTestId("dental-arch-map")).toHaveAttribute("data-map-state", "unavailable");
      await expect(page.getByTestId("missing-tooth-statement")).toHaveText("Identity/data not established");
      await expect(page.getByTestId("header-next-action")).toHaveText("Create Treatment Plan");
      const treatmentNav = page.getByRole("button", { name: /Treatment Setup/ });
      await expect(treatmentNav).toHaveAttribute("title", /blocked by environment/i);
      await shot(page, `${viewport.name}_03_blocked_segmentation`);
      await assertNoPageOverflow(page);

      const viewportBox = await page.getByTestId("layout-viewport").boundingBox();
      const inspector = await page.getByTestId("adaptive-inspector").boundingBox();
      expect(viewportBox && inspector && viewportBox.width > inspector.width).toBeTruthy();
    });
  }

  test("fixture map stays on tooth_ref and syncs selection", async ({ page }) => {
    await page.setViewportSize({ width: 1600, height: 1000 });
    await installApi(page, "fixture");
    await page.goto(WEB);
    await page.locator("#patient-reference").fill("wave3-fixture");
    await page.getByTestId("create-case-primary").click();
    await page.locator("#upper-stl").setInputFiles({
      name: "upper.stl",
      mimeType: "model/stl",
      buffer: Buffer.from("upper"),
    });
    await page.locator("#lower-stl").setInputFiles({
      name: "lower.stl",
      mimeType: "model/stl",
      buffer: Buffer.from("lower"),
    });
    await page.getByRole("button", { name: "Review segmentation" }).click();
    await expect(page.getByTestId("segmentation-review-strip")).toHaveAttribute(
      "data-segmentation-kind",
      "fixture_test_only",
    );
    await expect(page.getByTestId("segmentation-provenance")).toHaveText("Fixture / test-only");
    const upper = page.getByTestId("dental-map-upper:instance:0");
    await expect(upper).toBeVisible();
    await expect(upper).not.toHaveText(/FDI/);
    await upper.click();
    await expect(upper).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("adaptive-inspector")).toHaveAttribute("data-inspector-mode", "tooth");
    await expect(page.getByTestId("selection-count")).toHaveText("1 selected");
    await page.getByTestId("dental-map-lower:instance:0").click({ modifiers: ["Shift"] });
    await expect(page.getByTestId("selection-count")).toHaveText("2 selected");
    await page.getByTestId("tool-arch-upper").click();
    await expect(page.getByTestId("tool-arch-upper")).toHaveClass(/is-active/);
    await expect(page.getByTestId("tool-fit-case")).toBeVisible();
    await page.getByTestId("tool-fit-selection").click();
    await expect(page.getByRole("button", { name: "Measure" })).toHaveCount(0);
    await shot(page, "1600x1000_04_fixture_selection");
  });
});
