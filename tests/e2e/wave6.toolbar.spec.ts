/**
 * Wave 6 browser QA.
 *
 * UI evidence only. Fixture crowns are generated test meshes.
 * They are not clinical segmentation, not a treatment recommendation, and not ToothInstanceNet output.
 *
 * Requires the web app at P8_WEB_URL (default http://127.0.0.1:5173).
 */
import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEB = process.env.P8_WEB_URL ?? "http://127.0.0.1:5173";
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const EVIDENCE_DIR = path.join(ROOT, ".research/tmp/wave6_browser_qa");

const VIEWPORTS = [
  { width: 1366, height: 768, name: "1366x768" },
  { width: 1600, height: 1000, name: "1600x1000" },
  { width: 1280, height: 800, name: "1280x800" },
] as const;

type Provenance = "ui_shell" | "blocked" | "fixture_test_only" | "failure" | "unavailable";

const images: Array<{
  file: string;
  viewport: string;
  provenance: Provenance;
  geometry: string;
  context: string;
  clinicalSegmentationValidation: false;
  note: string;
}> = [];

const occupancy: Array<Record<string, unknown>> = [];

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
      vertices.push([cx + Math.cos(theta) * radius * 0.8, cy + y, cz + Math.sin(theta) * radius]);
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

function movement() {
  return {
    translationX: 0,
    translationY: 0,
    translationZ: 0,
    rotation: 0,
    tip: 0,
    torque: 0,
    angulation: 0,
    intrusion: 0,
    extrusion: 0,
  };
}

function treatmentTooth(arch: "upper" | "lower", index: number, stageShift: number) {
  const mesh = crown(arch, index);
  return {
    instanceId: mesh.instance_id,
    fdiNumber: null,
    toothRef: mesh.tooth_ref,
    planningMode: "semantic_only_experimental",
    arch,
    confidence: 0,
    vertices: mesh.vertices.map((vertex) => [vertex[0] + stageShift, vertex[1], vertex[2]]),
    faces: mesh.faces,
    centroid: [mesh.centroid[0] + stageShift, mesh.centroid[1], mesh.centroid[2]],
    identificationStatus: "uncertain",
    movement: { ...movement(), translationX: stageShift },
    validationStatus: "unavailable",
    validationMessage: "Fixture/test-only surface. Not a clinical finding.",
    provenance: "fixture",
    fixture: true,
    experimental: true,
  };
}

function treatmentBundle() {
  const teethFor = (shift: number) => [
    ...Array.from({ length: 4 }, (_, index) => treatmentTooth("upper", index, shift)),
    ...Array.from({ length: 4 }, (_, index) => treatmentTooth("lower", index, shift)),
  ];
  return {
    stages: [
      {
        index: 0,
        stageId: "fixture-stage-0",
        teeth: teethFor(0),
        validationStatus: "warning",
        collisionCount: 0,
        proximityCount: 0,
        contactCount: 0,
        warnings: ["Fixture finding. Not a clinical approval."],
        provenance: "fixture",
        fixture: true,
      },
      {
        index: 1,
        stageId: "fixture-stage-1",
        teeth: teethFor(0.4),
        validationStatus: "warning",
        collisionCount: 0,
        proximityCount: 0,
        contactCount: 0,
        warnings: ["Fixture finding. Not a clinical approval."],
        provenance: "fixture",
        fixture: true,
      },
    ],
    provenance: "fixture",
    fixture: true,
    realDataAvailable: true,
    experimental: true,
    planningMode: "semantic_only_experimental",
    proposalKind: "original_generated",
    editHistory: [],
    iprSites: [],
    attachmentSites: [],
    sourceKind: "development_treatment_fixture",
    unavailableReason: "Browser QA fixture. Not clinical evidence.",
    smartStaging: {
      contract_version: "smart_staging_1.0",
      freshness: "stale",
      stage_count: 2,
      clinically_approved: false,
      clinically_optimal: false,
      meta: {
        staging_plan_id: "fixture-plan",
        staging_version_id: "fixture-version",
        parent_staging_version_id: null,
        source_setup_version_id: "fixture-setup",
        algorithm_name: "stored-staging",
        algorithm_version: "fixture",
        stage_count: 2,
        affected_tooth_count: 8,
        truth_state: "stale",
        freshness: "stale",
        limitations: ["Fixture staging. Not a clinical-quality claim."],
        clinically_approved: false,
        clinically_optimal: false,
      },
    },
    validationSummary: {
      geometry: "unavailable",
      contacts: "unavailable",
      proximity: "unavailable",
      collisions: "unavailable",
      movementConstraints: "unavailable",
      stageConsistency: "unavailable",
      dataCompleteness: "unavailable",
      provenance: "unavailable",
      doctorReview: "required",
      findings: ["Fixture finding. Not a score and not an approval."],
    },
  };
}

function processingBody(status: string, message: string) {
  return {
    job_id: "wave6-job",
    case_id: "wave6-case",
    overall_progress: null,
    current_stage: status === "COMPLETED" ? "LOADING_TREATMENT" : "SEGMENTING_LOWER",
    stage_status: status,
    stage_progress: null,
    completed_stages: status === "COMPLETED" ? ["SEGMENTING_LOWER"] : [],
    pending_stages: status === "PROCESSING" ? ["BUILDING_PLAN"] : [],
    error_state: status === "FAILED",
    error_code: status === "FAILED" ? "DECODER_STOPPED" : null,
    user_message: message,
    started_at: "2026-09-26T00:00:00Z",
    updated_at: "2026-09-26T00:00:04Z",
    completed_at: null,
    elapsed_seconds: 4,
  };
}

async function installApi(
  page: Page,
  mode: "blocked" | "fixture" | "failed" | "treatment" | "unavailable",
): Promise<void> {
  let polls = 0;
  await page.route("**/cases**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    if (method === "POST" && /\/cases$/.test(url)) {
      await route.fulfill({
        json: {
          id: "wave6-case",
          patient_reference: "wave6-toolbar",
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
          id: "wave6-case",
          patient_reference: "wave6-toolbar",
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
      await route.fulfill({ json: { is_valid: true, triangle_count: 12, is_watertight: true, errors: [] } });
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
      if (mode === "unavailable") {
        await route.fulfill({
          json: {
            state: "model_unavailable",
            segmentation_truth_state: "not_available",
            source_kind: "uploaded_real_case",
            segmentation_runtime_ms: null,
            total_runtime_ms: 1,
            tooth_instance_count: 0,
            validation_findings: [],
            failures: ["Segmentation model is not available."],
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
    if (method === "GET" && url.includes("/dental-intelligence")) {
      await route.fulfill({ status: 404, body: "none" });
      return;
    }
    if (method === "GET" && /\/treatment$/.test(url)) {
      await route.fulfill({ json: treatmentBundle() });
      return;
    }
    if (method === "POST" && /\/processing$/.test(url)) {
      await route.fulfill({
        json: processingBody("PROCESSING", "Segmenting lower arch"),
      });
      return;
    }
    if (method === "GET" && url.includes("processing-status")) {
      polls += 1;
      const next =
        mode === "failed"
          ? polls > 1
            ? "FAILED"
            : "PROCESSING"
          : mode === "treatment"
            ? polls > 1
              ? "COMPLETED"
              : "PROCESSING"
            : "PROCESSING";
      const message =
        next === "FAILED"
          ? "Decoder stopped on the lower arch."
          : next === "COMPLETED"
            ? "Fixture treatment loaded for UI review. Not clinical evidence."
            : "Segmenting lower arch";
      await route.fulfill({ json: processingBody(next, message) });
      return;
    }
    await route.fulfill({ status: 404, body: "unmocked" });
  });
}

async function shot(page: Page, name: string, provenance: Provenance, geometry: string, note: string): Promise<void> {
  fs.mkdirSync(EVIDENCE_DIR, { recursive: true });
  const file = `${name}.png`;
  await page.screenshot({ path: path.join(EVIDENCE_DIR, file), fullPage: false });
  const viewport = page.viewportSize();
  const context = await page.locator("[data-toolbar-context]").first().getAttribute("data-toolbar-context").catch(() => "none");
  images.push({
    file,
    viewport: viewport ? `${viewport.width}x${viewport.height}` : "unknown",
    provenance,
    geometry,
    context: context ?? "none",
    clinicalSegmentationValidation: false,
    note,
  });
}

async function assertViewportDominant(page: Page, label: string): Promise<void> {
  const metrics = await page.evaluate(() => {
    const read = (selector: string) => {
      const element = document.querySelector(selector);
      if (!element) return null;
      const rect = element.getBoundingClientRect();
      return {
        width: Math.round(rect.width),
        height: Math.round(rect.height),
        top: Math.round(rect.top),
        left: Math.round(rect.left),
      };
    };
    const primary = [...document.querySelectorAll("[data-testid='contextual-toolbar'] > [data-testid^='tool-']")].map(
      (element) => element.getAttribute("data-testid"),
    );
    return {
      scrollHeight: document.documentElement.scrollHeight,
      clientHeight: document.documentElement.clientHeight,
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      viewport: read("[data-testid='layout-viewport']"),
      toolbar: read("[data-testid='contextual-toolbar']"),
      widgets: read("[data-testid='smart-widgets']"),
      inspector: read("[data-testid='adaptive-inspector']"),
      context: document.querySelector("[data-toolbar-context]")?.getAttribute("data-toolbar-context") ?? "none",
      primary,
      statusCount: document.querySelectorAll("[data-status-surface='primary']").length,
    };
  });
  expect(metrics.scrollHeight).toBeLessThanOrEqual(metrics.clientHeight + 4);
  expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.clientWidth + 4);
  expect(metrics.statusCount).toBe(1);
  if (metrics.viewport && metrics.inspector) {
    expect(metrics.viewport.width).toBeGreaterThan(metrics.inspector.width);
  }
  if (metrics.viewport && metrics.toolbar) {
    expect(metrics.toolbar.height).toBeLessThan(metrics.viewport.height * 0.34);
    expect(metrics.toolbar.left).toBeGreaterThanOrEqual(metrics.viewport.left - 2);
  }
  occupancy.push({ label, ...metrics });
}

async function importScans(page: Page): Promise<void> {
  await page.locator("#patient-reference").fill("wave6");
  await page.getByTestId("create-case-primary").click();
  await page.locator("#upper-stl").setInputFiles({
    name: "upper.stl",
    mimeType: "model/stl",
    buffer: Buffer.from("upper-wave6"),
  });
  await page.locator("#lower-stl").setInputFiles({
    name: "lower.stl",
    mimeType: "model/stl",
    buffer: Buffer.from("lower-wave6"),
  });
}

test.describe.configure({ mode: "serial" });

test.describe("Wave 6 contextual toolbar", () => {
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
    const evidencePath = path.join(EVIDENCE_DIR, "evidence.json");
    let priorImages: typeof images = [];
    let priorOccupancy: typeof occupancy = [];
    if (fs.existsSync(evidencePath)) {
      try {
        const prior = JSON.parse(fs.readFileSync(evidencePath, "utf8")) as {
          images?: typeof images;
          occupancy?: typeof occupancy;
        };
        priorImages = prior.images ?? [];
        priorOccupancy = prior.occupancy ?? [];
      } catch {
        priorImages = [];
        priorOccupancy = [];
      }
    }
    const imageByFile = new Map<string, (typeof images)[number]>();
    for (const image of [...priorImages, ...images]) imageByFile.set(image.file, image);
    const occupancyByLabel = new Map<string, (typeof occupancy)[number]>();
    for (const entry of [...priorOccupancy, ...occupancy]) {
      const label = String(entry.label ?? "");
      if (label) occupancyByLabel.set(label, entry);
    }
    fs.writeFileSync(
      evidencePath,
      JSON.stringify(
        {
          wave: 6,
          clinicalSegmentationValidation: false,
          liveToothInstanceNet: false,
          fixtureEvidence: "non-clinical",
          note: "Screenshots are UI evidence. Fixture crowns and the fixture treatment bundle are generated test meshes. They are not patient inference, not an approval, and not a safety result. Blocked shots are an environment blocker, not a model failure and not zero teeth. WP-14 and WP-15 were not exercised.",
          viewports: VIEWPORTS,
          images: [...imageByFile.values()],
          occupancy: [...occupancyByLabel.values()],
        },
        null,
        2,
      ),
    );
  });

  for (const viewport of VIEWPORTS) {
    test(`idle, case, blocked, and unavailable at ${viewport.name}`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await installApi(page, "blocked");
      await page.goto(WEB);
      await expect(page.locator("[data-toolbar-context]").first()).toHaveAttribute("data-toolbar-context", "idle");
      await expect(page.getByTestId("tool-fit-case")).toHaveCount(0);
      await expect(page.getByTestId("provenance-widget")).toHaveCount(0);
      await expect(page.getByTestId("selection-widget")).toHaveCount(0);
      await shot(page, `${viewport.name}_01_idle`, "ui_shell", "none", "Idle. No selection and no scene. No clinical tools.");
      await assertViewportDominant(page, `${viewport.name}-idle`);

      await page.locator("#patient-reference").fill("wave6-case");
      await page.getByTestId("create-case-primary").click();
      await expect(page.locator("[data-toolbar-context]").first()).toHaveAttribute("data-toolbar-context", "case");
      await shot(page, `${viewport.name}_02_case`, "ui_shell", "none", "Case intake. Toolbar stays on case context.");
      await assertViewportDominant(page, `${viewport.name}-case`);

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
        { timeout: 20_000 },
      );
      await expect(page.locator("[data-toolbar-context]").first()).toHaveAttribute("data-toolbar-context", "blocked");
      await expect(page.getByTestId("tool-retry-segmentation")).toHaveCount(0);
      await expect(page.locator("[data-tool-id='retry-segmentation']")).toHaveAttribute("data-availability", "blocked");
      await expect(page.getByTestId("tool-measure")).toHaveCount(0);
      await shot(
        page,
        `${viewport.name}_03_blocked`,
        "blocked",
        "none",
        "Environment blocker. Retry is blocked, not a failed model, and is not a primary button.",
      );
      await assertViewportDominant(page, `${viewport.name}-blocked`);
    });

    test(`fixture selection, staging, processing, and failure at ${viewport.name}`, async ({ page }) => {
      test.setTimeout(180_000);
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await installApi(page, "failed");
      await page.goto(WEB);
      await importScans(page);
      await page.getByRole("button", { name: "Review segmentation" }).click();
      await expect(page.getByTestId("segmentation-review-strip")).toHaveAttribute(
        "data-segmentation-kind",
        "fixture_test_only",
        { timeout: 20_000 },
      );
      await expect(page.locator("[data-toolbar-context]").first()).toHaveAttribute("data-toolbar-context", "segmentation-review");
      await expect(page.getByTestId("tool-fit-case")).toBeVisible();
      await expect(page.getByTestId("tool-labels")).toBeVisible();
      await expect(page.getByTestId("tool-measure")).toHaveCount(0);
      await expect(page.getByTestId("provenance-widget")).toHaveCount(0);
      await shot(
        page,
        `${viewport.name}_04_fixture_review`,
        "fixture_test_only",
        "generated_fixture_crowns",
        "Fixture segmentation review. Provenance stays on the strip, not a second widget.",
      );

      await page.getByTestId("dental-map-upper:instance:0").click();
      await expect(page.locator("[data-toolbar-context]").first()).toHaveAttribute("data-toolbar-context", "one-tooth");
      await expect(page.getByTestId("selection-widget")).toContainText("Fixture / test-only");
      await expect(page.getByTestId("tool-fit-selection")).toBeVisible();
      await expect(page.getByTestId("selection-widget")).not.toContainText(/\bFDI\b/);
      await shot(
        page,
        `${viewport.name}_05_one_tooth`,
        "fixture_test_only",
        "generated_fixture_crowns",
        "One fixture tooth. Label is tooth_ref. No invented FDI.",
      );

      await page.getByTestId("dental-map-lower:instance:1").click({ modifiers: ["Shift"] });
      await expect(page.locator("[data-toolbar-context]").first()).toHaveAttribute("data-toolbar-context", "multi-tooth");
      await expect(page.getByTestId("selection-widget")).toContainText("2 teeth");
      await expect(page.getByTestId("tool-isolate")).toHaveCount(0);
      await shot(
        page,
        `${viewport.name}_06_multi_tooth`,
        "fixture_test_only",
        "generated_fixture_crowns",
        "Group selection. No invented group clinical action.",
      );

      await page.getByRole("button", { name: "Treatment Setup" }).click();
      await expect(page.locator("[data-toolbar-context]").first()).toHaveAttribute("data-toolbar-context", /treatment-setup|multi-tooth/);
      await expect(page.getByTestId("current-target-widget")).toHaveCount(0);
      await shot(
        page,
        `${viewport.name}_07_treatment_setup`,
        "fixture_test_only",
        "generated_fixture_crowns",
        "Treatment setup before a stored target. Current/target widget stays hidden.",
      );

      await page.getByRole("button", { name: "Staging" }).click();
      await shot(
        page,
        `${viewport.name}_08_staging_without_plan`,
        "fixture_test_only",
        "generated_fixture_crowns",
        "Staging step before stored stages. No stage-count claim.",
      );

      await page.getByRole("button", { name: "Treatment Setup" }).click();
      await page.getByRole("button", { name: "Generate Treatment Setup" }).click();
      await expect(page.getByTestId("case-loading-overlay")).toBeVisible();
      await expect(page.locator("[data-toolbar-context]").first()).toHaveAttribute("data-toolbar-context", "processing");
      await expect(page.getByTestId("tool-fit-case")).toHaveCount(0);
      await expect(page.getByTestId("tool-cancel-processing")).toHaveCount(0);
      await expect(page.getByTestId("cancel-processing")).toBeVisible();
      await expect(page.getByTestId("processing-widget")).toHaveCount(0);
      await shot(
        page,
        `${viewport.name}_09_processing`,
        "ui_shell",
        "none",
        "Processing. Overlay owns status and cancel. Toolbar has no clinical edits.",
      );

      await expect(page.getByTestId("primary-status")).toContainText(/failed/i, { timeout: 8_000 });
      await expect(page.locator("[data-toolbar-context]").first()).toHaveAttribute("data-toolbar-context", "failed");
      await expect(page.getByText("Decoder stopped on the lower arch.")).toBeVisible();
      await expect(page.getByTestId("tool-retry-segmentation")).toHaveCount(0);
      await shot(
        page,
        `${viewport.name}_10_failed`,
        "failure",
        "generated_fixture_crowns",
        "Processing failure text stays. Segmentation retry is not offered for this failure.",
      );
      await assertViewportDominant(page, `${viewport.name}-failed`);
    });

    test(`stale staging, refinement, validation, and production at ${viewport.name}`, async ({ page }) => {
      test.setTimeout(180_000);
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await installApi(page, "treatment");
      await page.goto(WEB);
      await importScans(page);
      await page.getByRole("button", { name: "Review segmentation" }).click();
      await expect(page.getByTestId("segmentation-review-strip")).toHaveAttribute(
        "data-segmentation-kind",
        "fixture_test_only",
        { timeout: 20_000 },
      );
      await page.getByRole("button", { name: "Treatment Setup" }).click();
      await page.getByRole("button", { name: "Generate Treatment Setup" }).click();
      await expect(page.getByTestId("staging-regenerate")).toBeVisible({ timeout: 20_000 });
      await expect(page.locator("[data-toolbar-context]").first()).toHaveAttribute("data-toolbar-context", "stale");
      await expect(page.getByTestId("tool-regenerate-staging")).toHaveCount(0);
      await expect(page.getByTestId("current-target-widget")).toContainText("Not an approval");
      await expect(page.getByTestId("staging-widget")).toHaveCount(0);
      await expect(page.getByText(/optimal/i)).toHaveCount(0);
      await shot(
        page,
        `${viewport.name}_11_stale_staging`,
        "fixture_test_only",
        "generated_fixture_treatment",
        "Fixture staging is stale. Regenerate stays on the staging step. Not a clinical-quality claim.",
      );

      await page.getByRole("button", { name: "Refinement" }).click();
      await expect(page.locator("[data-toolbar-context]").first()).toHaveAttribute("data-toolbar-context", "refinement");
      await expect(page.locator("[data-tool-id='move']")).toHaveAttribute("data-availability", "unavailable");
      await shot(
        page,
        `${viewport.name}_12_refinement`,
        "fixture_test_only",
        "generated_fixture_treatment",
        "Refinement. Move stays unavailable until a tooth is selected on the existing tooth controls.",
      );

      await page.getByRole("button", { name: "Validation" }).click();
      await expect(page.locator("[data-toolbar-context]").first()).toHaveAttribute("data-toolbar-context", "validation");
      await expect(page.getByTestId("tool-validation-overlay")).toHaveCount(0);
      await expect(page.locator("[data-tool-id='validation-overlay']")).toHaveAttribute("data-availability", "unavailable");
      await expect(page.getByText(/\bsafe\b/i)).toHaveCount(0);
      await shot(
        page,
        `${viewport.name}_13_validation`,
        "fixture_test_only",
        "generated_fixture_treatment",
        "Validation. Overlay is unavailable. No safe score.",
      );

      await page.getByRole("button", { name: "Production" }).click();
      await expect(page.locator("[data-toolbar-context]").first()).toHaveAttribute("data-toolbar-context", "production");
      await shot(
        page,
        `${viewport.name}_14_production`,
        "fixture_test_only",
        "generated_fixture_treatment",
        "Production. No new manufacturing action was added to the toolbar.",
      );
      await assertViewportDominant(page, `${viewport.name}-production`);
    });

    test(`unavailable segmentation at ${viewport.name}`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await installApi(page, "unavailable");
      await page.goto(WEB);
      await importScans(page);
      await page.getByRole("button", { name: "Review segmentation" }).click();
      await expect(page.getByTestId("segmentation-review-strip")).toHaveAttribute(
        "data-segmentation-kind",
        "not_available",
        { timeout: 20_000 },
      );
      await expect(page.locator("[data-toolbar-context]").first()).toHaveAttribute("data-toolbar-context", "unavailable");
      await expect(page.getByTestId("tool-measure")).toHaveCount(0);
      await expect(page.locator("[data-tool-id='measure']")).toHaveAttribute("data-availability", "unavailable");
      await shot(
        page,
        `${viewport.name}_15_unavailable`,
        "unavailable",
        "none",
        "Segmentation is not available. Measure is explained, not presented as a broken button.",
      );
      await assertViewportDominant(page, `${viewport.name}-unavailable`);
    });
  }
});
