/**
 * Wave 5 browser QA.
 *
 * UI evidence only. Fixture crowns are generated test meshes.
 * Blocked shots are not a tooth count of zero and are not live ToothInstanceNet output.
 *
 * Requires the web app at P8_WEB_URL (default http://127.0.0.1:5173).
 */
import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEB = process.env.P8_WEB_URL ?? "http://127.0.0.1:5173";
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const EVIDENCE_DIR = path.join(ROOT, ".research/tmp/wave5_browser_qa");

const VIEWPORTS = [
  { width: 1366, height: 768, name: "1366x768" },
  { width: 1600, height: 1000, name: "1600x1000" },
  { width: 1280, height: 800, name: "1280x800" },
] as const;

type Provenance = "ui_shell" | "blocked" | "fixture_test_only" | "failure";

const images: Array<{
  file: string;
  viewport: string;
  provenance: Provenance;
  geometry: string;
  clinicalSegmentationValidation: false;
  note: string;
}> = [];

const performanceNotes: Array<{ viewport: string; action: string; milliseconds: number }> = [];
const stateNotes: Array<Record<string, string>> = [];

function crown(arch: "upper" | "lower", index: number) {
  const span = 4;
  const t = index / (span - 1);
  const angle = (t - 0.5) * 1.05;
  const arc = 16;
  const cx = Math.sin(angle) * arc;
  const cz = (Math.cos(angle) - 1) * arc * 0.65;
  const cy = arch === "upper" ? 6 : -6;
  const vertices: number[][] = [];
  const faces: number[][] = [];
  const segments = 8;
  const rings = 4;
  for (let ring = 0; ring <= rings; ring += 1) {
    const v = ring / rings;
    const y = (v - 0.35) * 4.4;
    const radius = 0.5 + Math.sin(Math.PI * v) * 1.05;
    for (let segment = 0; segment < segments; segment += 1) {
      const theta = (segment / segments) * Math.PI * 2;
      vertices.push([
        cx + Math.cos(theta) * radius * 0.8,
        cy + y,
        cz + Math.sin(theta) * radius,
      ]);
    }
  }
  for (let ring = 0; ring < rings; ring += 1) {
    for (let segment = 0; segment < segments; segment += 1) {
      const a = ring * segments + segment;
      const b = ring * segments + ((segment + 1) % segments);
      const c = (ring + 1) * segments + segment;
      const d = (ring + 1) * segments + ((segment + 1) % segments);
      faces.push([a, c, b], [b, c, d]);
    }
  }
  return {
    instance_id: (arch === "upper" ? 0 : 20) + index,
    tooth_ref: `${arch}:instance:${index}`,
    fdi_number: null,
    arch,
    vertices,
    faces,
    centroid: [cx, cy, cz],
    confidence: null,
    provenance: "fixture",
    fixture: true,
    experimental: true,
    planning_mode: "semantic_only_experimental",
    identification_status: "uncertain",
  };
}

async function shot(page: Page, name: string, provenance: Provenance, geometry: string, note: string): Promise<void> {
  fs.mkdirSync(EVIDENCE_DIR, { recursive: true });
  const file = `${name}.png`;
  await page.screenshot({ path: path.join(EVIDENCE_DIR, file), fullPage: false });
  const viewport = page.viewportSize();
  images.push({
    file,
    viewport: viewport ? `${viewport.width}x${viewport.height}` : "unknown",
    provenance,
    geometry,
    clinicalSegmentationValidation: false,
    note,
  });
}

async function installApi(page: Page, mode: "blocked" | "fixture"): Promise<void> {
  let polls = 0;
  await page.route("**/cases**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    if (method === "POST" && /\/cases$/.test(url)) {
      await route.fulfill({
        json: {
          id: "wave5-case",
          patient_reference: "wave5-smart-ui",
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
          id: "wave5-case",
          patient_reference: "wave5-smart-ui",
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
          tooth_instance_count: 4,
          identification_confidence: null,
          identified_teeth: 0,
          uncertain_teeth: 4,
          unidentified_teeth: 4,
          validation_findings: [],
          failures: [],
          arch_analysis_available: false,
          notes: ["fixture presentation crowns"],
          provenance: "fixture",
          fixture: true,
          experimental: true,
          tooth_instances: Array.from({ length: 4 }, (_, index) => crown(arch, index)),
        },
      });
      return;
    }
    if (method === "POST" && /\/processing$/.test(url)) {
      await route.fulfill({
        json: {
          job_id: "wave5-job",
          case_id: "wave5-case",
          overall_progress: null,
          current_stage: "SEGMENTING_LOWER",
          stage_status: "PROCESSING",
          stage_progress: null,
          completed_stages: [],
          pending_stages: ["BUILDING_PLAN"],
          error_state: false,
          error_code: null,
          user_message: "Segmenting lower arch",
          started_at: "2026-09-26T00:00:00Z",
          updated_at: "2026-09-26T00:00:02Z",
          completed_at: null,
          elapsed_seconds: 2,
        },
      });
      return;
    }
    if (method === "GET" && url.includes("processing-status")) {
      polls += 1;
      const failed = polls > 1;
      await route.fulfill({
        json: failed
          ? {
              job_id: "wave5-job",
              case_id: "wave5-case",
              overall_progress: null,
              current_stage: "SEGMENTING_LOWER",
              stage_status: "FAILED",
              stage_progress: null,
              completed_stages: [],
              pending_stages: [],
              error_state: true,
              error_code: "DECODER_STOPPED",
              user_message: "Decoder stopped on the lower arch.",
              started_at: "2026-09-26T00:00:00Z",
              updated_at: "2026-09-26T00:00:04Z",
              completed_at: null,
              elapsed_seconds: 4,
            }
          : {
              job_id: "wave5-job",
              case_id: "wave5-case",
              overall_progress: null,
              current_stage: "SEGMENTING_LOWER",
              stage_status: "PROCESSING",
              stage_progress: null,
              completed_stages: [],
              pending_stages: ["BUILDING_PLAN"],
              error_state: false,
              error_code: null,
              user_message: "Segmenting lower arch",
              started_at: "2026-09-26T00:00:00Z",
              updated_at: "2026-09-26T00:00:02Z",
              completed_at: null,
              elapsed_seconds: 2,
            },
      });
      return;
    }
    if (method === "POST" && url.includes("/processing/cancel")) {
      await route.fulfill({
        json: {
          job_id: "wave5-job",
          case_id: "wave5-case",
          overall_progress: null,
          current_stage: "SEGMENTING_LOWER",
          stage_status: "CANCELLED",
          stage_progress: null,
          completed_stages: [],
          pending_stages: [],
          error_state: false,
          error_code: null,
          user_message: "Processing was cancelled.",
          started_at: "2026-09-26T00:00:00Z",
          updated_at: "2026-09-26T00:00:03Z",
          completed_at: null,
          elapsed_seconds: 3,
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

async function importScans(page: Page): Promise<void> {
  await page.locator("#patient-reference").fill("wave5");
  await page.getByTestId("create-case-primary").click();
  await page.locator("#upper-stl").setInputFiles({
    name: "upper.stl",
    mimeType: "model/stl",
    buffer: Buffer.from("upper-wave5"),
  });
  await page.locator("#lower-stl").setInputFiles({
    name: "lower.stl",
    mimeType: "model/stl",
    buffer: Buffer.from("lower-wave5"),
  });
}

test.describe.configure({ mode: "serial" });

test.describe("Wave 5 smart UI", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      try {
        sessionStorage.clear();
      } catch {
        /* ignore */
      }
    });
  });

  test.afterAll(() => {
    fs.mkdirSync(EVIDENCE_DIR, { recursive: true });
    fs.writeFileSync(
      path.join(EVIDENCE_DIR, "evidence.json"),
      JSON.stringify(
        {
          wave: 5,
          clinicalSegmentationValidation: false,
          liveToothInstanceNet: false,
          fixtureEvidence: "non-clinical",
          note: "Screenshots are UI evidence. Fixture crowns are generated test meshes. Blocked shots are not a tooth count of zero. No patient STL was loaded. WP-14 and WP-15 were not exercised.",
          viewports: VIEWPORTS,
          images,
          performance: performanceNotes,
          states: stateNotes,
        },
        null,
        2,
      ),
    );
  });

  for (const viewport of VIEWPORTS) {
    test(`launch, intake, and blocked segmentation at ${viewport.name}`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await installApi(page, "blocked");
      await page.goto(WEB);
      await expect(page.getByTestId("primary-status")).toHaveCount(1);
      await expect(page.locator("[data-status-surface='primary']")).toHaveCount(1);
      await expect(page.locator("[data-readiness-surface='primary']")).toHaveCount(1);
      await shot(page, `${viewport.name}_01_launch`, "ui_shell", "none", "Launch. No case. Create Case is the step action.");
      await assertNoPageOverflow(page);

      const started = Date.now();
      await page.locator("#patient-reference").fill("wave5-blocked");
      await page.getByTestId("create-case-primary").click();
      await expect(page.getByTestId("case-intake-panel")).toHaveAttribute("data-case-state", "active");
      await expect(page.getByTestId("header-next-action")).toHaveText(/Import/);
      await expect(page.getByTestId("crown-stl-limitation")).toBeVisible();
      performanceNotes.push({
        viewport: viewport.name,
        action: "create-case-to-import-action",
        milliseconds: Date.now() - started,
      });
      await shot(page, `${viewport.name}_02_case_intake`, "ui_shell", "none", "Case intake. Crown STL limitation is visible. No bite-registration control.");

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
      const reviewStart = Date.now();
      await page.getByRole("button", { name: "Review segmentation" }).click();
      await expect(page.getByTestId("segmentation-review-strip")).toHaveAttribute(
        "data-segmentation-kind",
        "blocked_by_environment",
        { timeout: 20_000 },
      );
      await expect(page.getByTestId("primary-status")).toContainText(/environment blocker/i);
      await expect(page.getByTestId("adaptive-inspector")).toHaveAttribute("data-inspector-mode", "blocked");
      await expect(page.getByTestId("analysis-tooth-count")).toHaveText("Not available");
      await expect(page.locator("canvas")).toHaveCount(0);
      performanceNotes.push({
        viewport: viewport.name,
        action: "blocked-segmentation-review",
        milliseconds: Date.now() - reviewStart,
      });
      await shot(
        page,
        `${viewport.name}_03_blocked_segmentation`,
        "blocked",
        "none",
        "Environment blocker. Not a model failure and not zero teeth.",
      );
      const validationTitle = await page.getByRole("button", { name: "Validation" }).getAttribute("title");
      const productionTitle = await page.getByRole("button", { name: "Production" }).getAttribute("title");
      const stagingTitle = await page.getByRole("button", { name: "Staging" }).getAttribute("title");
      stateNotes.push({
        viewport: viewport.name,
        validation: validationTitle ?? "",
        production: productionTitle ?? "",
        staging: stagingTitle ?? "",
        next: await page.getByTestId("workflow-next").innerText(),
      });
      const stagingButton = page.getByRole("button", { name: "Staging" });
      if (await stagingButton.isEnabled()) await stagingButton.click();
      await shot(
        page,
        `${viewport.name}_04_staging_dependency`,
        "blocked",
        "none",
        "Staging opened only if the step is enabled. Dependency text stays in the workflow line.",
      );
      await assertNoPageOverflow(page);
      const viewportBox = await page.getByTestId("layout-viewport").boundingBox();
      const inspector = await page.getByTestId("adaptive-inspector").boundingBox();
      expect(viewportBox && inspector && viewportBox.width > inspector.width).toBeTruthy();
    });

    test(`fixture review, selection, and failure at ${viewport.name}`, async ({ page }) => {
      test.setTimeout(180_000);
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await installApi(page, "fixture");
      await page.goto(WEB);
      await importScans(page);
      const selectStart = Date.now();
      await page.getByRole("button", { name: "Review segmentation" }).click();
      await expect(page.getByTestId("segmentation-review-strip")).toHaveAttribute(
        "data-segmentation-kind",
        "fixture_test_only",
        { timeout: 20_000 },
      );
      await expect(page.getByTestId("segmentation-provenance")).toHaveText("Fixture / test-only");
      await expect(page.getByTestId("header-next-action")).toHaveText("Review unresolved identities");
      await expect(page.locator("canvas")).toBeVisible();
      await page.waitForTimeout(400);
      await shot(
        page,
        `${viewport.name}_05_fixture_review`,
        "fixture_test_only",
        "generated_fixture_crowns",
        "Fixture crowns. Not clinical segmentation validation.",
      );

      await page.getByTestId("dental-map-upper:instance:0").click();
      await expect(page.getByTestId("adaptive-inspector")).toHaveAttribute("data-inspector-mode", "tooth");
      await expect(page.getByTestId("selection-widget")).toBeVisible();
      await expect(page.getByText("Fixture / test-only").first()).toBeVisible();
      performanceNotes.push({
        viewport: viewport.name,
        action: "select-tooth-inspector",
        milliseconds: Date.now() - selectStart,
      });
      await shot(
        page,
        `${viewport.name}_06_selected_tooth`,
        "fixture_test_only",
        "generated_fixture_crowns",
        "One unresolved fixture tooth. No invented FDI.",
      );

      await page.getByTestId("dental-map-lower:instance:1").click({ modifiers: ["Shift"] });
      await expect(page.getByTestId("adaptive-inspector")).toHaveAttribute("data-inspector-mode", "group");
      await shot(
        page,
        `${viewport.name}_07_multi_selection`,
        "fixture_test_only",
        "generated_fixture_crowns",
        "Multi-selection. Shared clinical actions are not invented.",
      );

      await page.getByRole("button", { name: "Treatment Setup" }).click();
      await shot(
        page,
        `${viewport.name}_08_treatment_dependency`,
        "fixture_test_only",
        "generated_fixture_crowns",
        "Treatment setup step. No stored target is implied as approved.",
      );

      await page.getByRole("button", { name: "Generate Treatment Setup" }).click();
      await expect(page.getByTestId("case-loading-overlay")).toBeVisible();
      await expect(page.getByTestId("cancel-processing")).toBeVisible();
      await expect(page.getByText("No reliable remaining-time estimate")).toBeVisible();
      await shot(
        page,
        `${viewport.name}_09_processing`,
        "ui_shell",
        "none",
        "Indeterminate processing. Cancel is available. No invented remaining time.",
      );

      await expect(page.getByTestId("primary-status")).toContainText(/failed/i, { timeout: 8000 });
      await expect(page.getByText("Decoder stopped on the lower arch.")).toBeVisible();
      await shot(
        page,
        `${viewport.name}_10_failure`,
        "failure",
        "none",
        "Durable failure text is preserved. Not a generic error.",
      );
      await assertNoPageOverflow(page);
    });
  }
});
