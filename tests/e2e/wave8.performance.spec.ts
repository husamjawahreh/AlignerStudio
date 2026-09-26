/**
 * Wave 8 browser QA.
 *
 * UI evidence only. Fixture crowns are generated test meshes.
 * They are not clinical segmentation and not ToothInstanceNet output.
 *
 * Requires the web app at P8_WEB_URL (default http://127.0.0.1:5173).
 */
import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEB = process.env.P8_WEB_URL ?? "http://127.0.0.1:5173";
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const EVIDENCE_DIR = path.join(ROOT, ".research/tmp/wave8_browser_qa");
const NO_ESTIMATE = "No reliable remaining-time estimate";

const VIEWPORTS = [
  { width: 1366, height: 768, name: "1366x768" },
  { width: 1600, height: 1000, name: "1600x1000" },
  { width: 1280, height: 800, name: "1280x800" },
] as const;

type Provenance = "ui_shell" | "blocked" | "fixture_test_only" | "failure" | "unavailable" | "stale";

const images: Array<{
  file: string;
  viewport: string;
  provenance: Provenance;
  geometry: string;
  note: string;
}> = [];
const timings: Array<Record<string, unknown>> = [];

function crown(arch: "upper" | "lower", index: number) {
  const angle = (index / 3 - 0.5) * 1.05;
  const cx = Math.sin(angle) * 16;
  const cz = (Math.cos(angle) - 1) * 10;
  const cy = arch === "upper" ? 6 : -6;
  const vertices: number[][] = [];
  const faces: number[][] = [];
  for (let ring = 0; ring <= 3; ring += 1) {
    const v = ring / 3;
    const y = (v - 0.35) * 4;
    const radius = 0.5 + Math.sin(Math.PI * v);
    for (let segment = 0; segment < 6; segment += 1) {
      const theta = (segment / 6) * Math.PI * 2;
      vertices.push([cx + Math.cos(theta) * radius, cy + y, cz + Math.sin(theta) * radius]);
    }
  }
  for (let ring = 0; ring < 3; ring += 1) {
    for (let segment = 0; segment < 6; segment += 1) {
      const a = ring * 6 + segment;
      const b = ring * 6 + ((segment + 1) % 6);
      const c = (ring + 1) * 6 + segment;
      const d = (ring + 1) * 6 + ((segment + 1) % 6);
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
    translationX: 0, translationY: 0, translationZ: 0, rotation: 0, tip: 0, torque: 0, angulation: 0, intrusion: 0, extrusion: 0,
  };
}

function treatmentTooth(arch: "upper" | "lower", index: number, shift: number) {
  const mesh = crown(arch, index);
  return {
    instanceId: mesh.instance_id,
    fdiNumber: null,
    toothRef: mesh.tooth_ref,
    planningMode: "semantic_only_experimental",
    arch,
    confidence: 0,
    vertices: mesh.vertices.map((vertex) => [vertex[0] + shift, vertex[1], vertex[2]]),
    faces: mesh.faces,
    centroid: [mesh.centroid[0] + shift, mesh.centroid[1], mesh.centroid[2]],
    identificationStatus: "uncertain",
    movement: { ...movement(), translationX: shift },
    validationStatus: "unavailable",
    validationMessage: "Fixture/test-only surface. Not a clinical finding.",
    provenance: "fixture",
    fixture: true,
    experimental: true,
  };
}

function treatmentBundle(stale: boolean) {
  const teethFor = (shift: number) => [
    ...Array.from({ length: 4 }, (_, index) => treatmentTooth("upper", index, shift)),
    ...Array.from({ length: 4 }, (_, index) => treatmentTooth("lower", index, shift)),
  ];
  const freshness = stale ? "stale" : "current";
  return {
    stages: [0, 1].map((index) => ({
      index,
      stageId: `fixture-stage-${index}`,
      teeth: teethFor(index * 0.4),
      validationStatus: "warning",
      collisionCount: 0,
      proximityCount: 0,
      contactCount: 0,
      warnings: ["Fixture finding. Not a clinical approval."],
      provenance: "fixture",
      fixture: true,
    })),
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
      freshness,
      stage_count: 2,
      clinically_approved: false,
      clinically_optimal: false,
      meta: { freshness, truth_state: freshness, clinically_approved: false, clinically_optimal: false },
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
    validationCapability: {
      freshness,
      summary: { finding_count: 1, checks_passed: 0, warnings: 1, errors: 0, unavailable_checks: 2, review_required_checks: 1 },
      checks: [{ check_state: "not_available", name: "manufacturing" }],
      findings: [{
        finding_id: "fixture-finding",
        category: "fixture",
        check_state: "requires_review",
        affected_tooth_refs: [],
        stage_index: 0,
        message: "Fixture finding. Not an approval.",
      }],
    },
  };
}

function noEstimate() {
  return {
    kind: "none",
    seconds: null,
    confidence: null,
    sample_count: 0,
    qualifier: "none",
    label: NO_ESTIMATE,
  };
}

function measuredEstimate() {
  return {
    kind: "measured",
    seconds: 75,
    low_seconds: 68,
    high_seconds: 82,
    confidence: 0.7,
    sample_count: 4,
    qualifier: "estimated",
    operation_id: "case-processing",
    input_class: "both-arches",
    label: "About 75 seconds remaining, estimated. Not a guarantee.",
  };
}

async function installApi(page: Page): Promise<{
  mode: { value: "blocked" | "fixture" | "failed" | "treatment" | "stale" };
  counts: { pipeline: number; processing: number; polls: number; regenerate: number; cancel: number; holdProcessing: boolean; showEstimate: boolean };
}> {
  const mode: { value: "blocked" | "fixture" | "failed" | "treatment" | "stale" } = { value: "blocked" };
  const counts = { pipeline: 0, processing: 0, polls: 0, regenerate: 0, cancel: 0, holdProcessing: false, showEstimate: false };
  let polls = 0;
  await page.route("**/cases**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    const caseBody = {
      id: "wave8-case",
      patient_reference: "wave8-performance",
      status: "mesh_validated",
      meshes: [
        { arch: "upper", file_path: "/tmp/upper.stl", original_filename: "upper.stl", uploaded_at: "2026-09-26T00:00:00Z" },
        { arch: "lower", file_path: "/tmp/lower.stl", original_filename: "lower.stl", uploaded_at: "2026-09-26T00:00:00Z" },
      ],
      created_at: "2026-09-26T00:00:00Z",
    };
    if (method === "POST" && /\/cases$/.test(url)) {
      await route.fulfill({ json: { ...caseBody, status: "created", meshes: [] } });
      return;
    }
    if (method === "GET" && /\/cases\/wave8-case$/.test(url)) {
      await route.fulfill({ json: caseBody });
      return;
    }
    if (method === "POST" && url.includes("/uploads") && !url.includes("validate")) {
      await route.fulfill({ json: caseBody });
      return;
    }
    if (method === "POST" && url.includes("/validate")) {
      await route.fulfill({ json: { is_valid: true, triangle_count: 12, is_watertight: true, errors: [] } });
      return;
    }
    if (method === "POST" && url.includes("/pipeline/")) {
      counts.pipeline += 1;
      const arch = url.includes("/lower") ? "lower" : "upper";
      if (mode.value === "blocked") {
        await route.fulfill({
          json: {
            state: "blocked_by_environment",
            segmentation_truth_state: "blocked_by_environment",
            source_kind: "uploaded_real_case",
            runtime_blocker: "No NVIDIA driver, torch, or pointops on this host.",
            segmentation_runtime_ms: null,
            total_runtime_ms: 1,
            tooth_instance_count: 0,
            validation_findings: [],
            failures: ["Live ToothInstanceNet inference did not run."],
            notes: [],
            provenance: "real",
            fixture: false,
            tooth_instances: [],
          },
        });
        return;
      }
      if (mode.value === "failed") {
        await route.fulfill({
          json: {
            state: "segmentation_failed",
            segmentation_truth_state: "failed",
            source_kind: "uploaded_real_case",
            segmentation_runtime_ms: 2,
            total_runtime_ms: 4,
            tooth_instance_count: 0,
            validation_findings: [],
            failures: ["Decoder stopped."],
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
          identified_teeth: 0,
          uncertain_teeth: 4,
          unidentified_teeth: 4,
          validation_findings: [],
          failures: [],
          notes: ["fixture presentation crowns"],
          provenance: "fixture",
          fixture: true,
          experimental: true,
          tooth_instances: Array.from({ length: 4 }, (_, index) => crown(arch, index)),
        },
      });
      return;
    }
    if (method === "POST" && url.includes("/staging/regenerate")) {
      counts.regenerate += 1;
      await route.fulfill({ json: treatmentBundle(mode.value === "stale") });
      return;
    }
    if (method === "GET" && /\/treatment$/.test(url)) {
      if (mode.value === "treatment" || mode.value === "stale") {
        await route.fulfill({ json: treatmentBundle(mode.value === "stale") });
        return;
      }
      await route.fulfill({ status: 404, body: "none" });
      return;
    }
    if (method === "POST" && url.includes("/processing/cancel")) {
      counts.cancel += 1;
      counts.holdProcessing = false;
      await route.fulfill({
        json: {
          job_id: "wave8-job",
          stage_status: "CANCELLED",
          current_stage: "preparation",
          user_message: "Case analysis was cancelled",
          overall_progress: null,
          elapsed_seconds: polls,
          remaining_time: noEstimate(),
        },
      });
      return;
    }
    if (method === "POST" && /\/processing$/.test(url)) {
      counts.processing += 1;
      polls = 0;
      counts.polls = 0;
      await route.fulfill({
        json: {
          job_id: "wave8-job",
          stage_status: "PROCESSING",
          current_stage: "preparation",
          user_message: "Preparing the case.",
          overall_progress: null,
          elapsed_seconds: 1,
          remaining_time: noEstimate(),
        },
      });
      return;
    }
    if (method === "GET" && url.includes("processing-status")) {
      polls += 1;
      counts.polls = polls;
      const done = polls > 1 && !counts.holdProcessing;
      const status = !done ? "PROCESSING" : mode.value === "failed" ? "FAILED" : "COMPLETED";
      await route.fulfill({
        json: {
          job_id: "wave8-job",
          stage_status: status,
          current_stage: status === "FAILED" ? "failed" : "preparation",
          user_message: status === "FAILED" ? "The run failed." : status === "COMPLETED" ? "Stored for review." : "Preparing the case.",
          overall_progress: null,
          elapsed_seconds: polls,
          error_code: status === "FAILED" ? "decoder" : null,
          remaining_time: status === "PROCESSING" && counts.showEstimate ? measuredEstimate() : noEstimate(),
        },
      });
      return;
    }
    if (method === "GET" && url.includes("/dental-intelligence")) {
      await route.fulfill({ status: 404, body: "none" });
      return;
    }
    await route.fulfill({ status: 404, body: "unmocked" });
  });
  return { mode, counts };
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
    note,
  });
}

async function assertShell(page: Page): Promise<void> {
  await expect(page.locator("[aria-current='step']")).toHaveCount(1);
  const scroll = await page.evaluate(() => ({
    height: document.documentElement.scrollHeight,
    client: document.documentElement.clientHeight,
    width: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(scroll.height).toBeLessThanOrEqual(scroll.client + 4);
  expect(scroll.width).toBeLessThanOrEqual(scroll.clientWidth + 4);
}

async function importScans(page: Page): Promise<void> {
  await page.locator("#patient-reference").fill("wave8");
  await page.getByTestId("create-case-primary").click();
  await page.locator("#upper-stl").setInputFiles({ name: "upper.stl", mimeType: "model/stl", buffer: Buffer.from("upper-wave8") });
  await page.locator("#lower-stl").setInputFiles({ name: "lower.stl", mimeType: "model/stl", buffer: Buffer.from("lower-wave8") });
}

test.describe.configure({ mode: "serial" });

test.describe("Wave 8 performance UX", () => {
  test.afterAll(() => {
    fs.mkdirSync(EVIDENCE_DIR, { recursive: true });
    const evidencePath = path.join(EVIDENCE_DIR, "evidence.json");
    let priorImages: typeof images = [];
    let priorTimings: typeof timings = [];
    if (fs.existsSync(evidencePath)) {
      try {
        const prior = JSON.parse(fs.readFileSync(evidencePath, "utf8")) as { images?: typeof images; timings?: typeof timings };
        priorImages = prior.images ?? [];
        priorTimings = prior.timings ?? [];
      } catch {
        priorImages = [];
        priorTimings = [];
      }
    }
    const imageByFile = new Map<string, (typeof images)[number]>();
    for (const image of [...priorImages, ...images]) imageByFile.set(image.file, image);
    const timingByKey = new Map<string, (typeof timings)[number]>();
    for (const entry of [...priorTimings, ...timings]) timingByKey.set(`${String(entry.viewport)}:${String(entry.name)}`, entry);
    fs.writeFileSync(evidencePath, JSON.stringify({
      wave: 8,
      clinicalSegmentationValidation: false,
      liveToothInstanceNet: false,
      environment: "BLOCKED_BY_ENVIRONMENT",
      fixtureEvidence: "non-clinical",
      note: "Screenshots are UI evidence. Fixture crowns are generated test meshes. Remaining time is shown only from the mocked evidence payload, never invented by the page. WP-14 and WP-15 were not exercised.",
      viewports: VIEWPORTS,
      images: [...imageByFile.values()],
      timings: [...timingByKey.values()],
    }, null, 2));
  });

  for (const viewport of VIEWPORTS) {
    test(`workflow and processing at ${viewport.name}`, async ({ page }) => {
      test.setTimeout(180_000);
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      const api = await installApi(page);
      const started = Date.now();
      await page.goto(WEB);
      timings.push({ viewport: viewport.name, name: "launch", ms: Date.now() - started });
      await assertShell(page);
      await shot(page, `${viewport.name}_01_launch`, "ui_shell", "none", "Launch. No case and no processing.");

      await importScans(page);
      await shot(page, `${viewport.name}_02_case_intake`, "ui_shell", "none", "Case intake. Scans imported. No analysis started.");

      const pipelineBefore = api.counts.pipeline;
      const navStarted = Date.now();
      await page.getByRole("button", { name: "Analysis" }).click();
      await expect(page.getByTestId("analysis-panel")).toBeVisible();
      timings.push({ viewport: viewport.name, name: "analysis-navigation", ms: Date.now() - navStarted, pipelinePosts: api.counts.pipeline - pipelineBefore });
      expect(api.counts.pipeline).toBe(pipelineBefore);
      await shot(page, `${viewport.name}_03_analysis`, "ui_shell", "none", "Analysis opened without a segmentation run.");

      await page.getByTestId("analysis-panel").getByRole("button", { name: "Review segmentation" }).click();
      await expect(page.getByTestId("analysis-environment-block")).toBeVisible({ timeout: 20_000 });
      await shot(page, `${viewport.name}_04_analysis_blocked`, "blocked", "none", "Environment blocker. Not zero teeth.");

      await page.getByRole("button", { name: "Treatment Setup" }).click();
      await expect(page.getByTestId("treatment-target-empty")).toBeVisible();
      expect(api.counts.processing).toBe(0);
      await shot(page, `${viewport.name}_05_treatment_navigation`, "blocked", "none", "Opening treatment setup did not create a plan.");

      await page.evaluate(() => sessionStorage.clear());
      api.mode.value = "fixture";
      await page.goto(WEB);
      await importScans(page);
      await page.getByRole("button", { name: "Analysis" }).click();
      await page.getByTestId("analysis-panel").getByRole("button", { name: "Review segmentation" }).click();
      await expect(page.getByTestId("analysis-fixture-note")).toContainText(/test-only/i, { timeout: 20_000 });

      api.counts.holdProcessing = true;
      const processingBefore = api.counts.processing;
      await page.getByRole("button", { name: "Treatment Setup" }).click();
      await page.getByRole("button", { name: "Generate Treatment Setup" }).click();
      await expect(page.getByTestId("case-loading-overlay")).toBeVisible();
      await expect(page.getByTestId("remaining-time")).toHaveCount(1);
      await expect(page.getByTestId("remaining-time")).toHaveText(NO_ESTIMATE);
      await expect(page.getByText(/\b0 seconds remaining\b/)).toHaveCount(0);
      const pollsAtOverlay = api.counts.polls;
      await page.waitForTimeout(2200);
      expect(api.counts.polls - pollsAtOverlay).toBeGreaterThanOrEqual(1);
      expect(api.counts.polls - pollsAtOverlay).toBeLessThanOrEqual(4);
      expect(api.counts.processing).toBe(processingBefore + 1);
      await shot(page, `${viewport.name}_06_processing_no_estimate`, "ui_shell", "none", "Explicit plan creation. No remaining-time estimate without history.");

      await page.reload();
      await expect(page.getByTestId("case-loading-overlay")).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId("remaining-time")).toHaveText(NO_ESTIMATE);
      await shot(page, `${viewport.name}_15_refresh_processing`, "ui_shell", "none", "Refresh during processing keeps the job and does not invent an estimate.");

      api.counts.showEstimate = true;
      await expect(page.getByTestId("remaining-time")).toContainText(/estimated/i, { timeout: 5000 });
      await expect(page.getByTestId("remaining-time")).toHaveCount(1);
      await expect(page.getByText(/Not a guarantee/)).toBeVisible();
      await shot(page, `${viewport.name}_07_measured_estimate`, "ui_shell", "none", "Measured estimate from the status payload. One surface. Not a guarantee.");

      await page.getByTestId("cancel-processing").click();
      await expect(page.getByText("Case analysis was cancelled")).toBeVisible({ timeout: 10_000 });
      expect(api.counts.cancel).toBe(1);
      await expect(page.getByTestId("case-loading-overlay")).toHaveCount(0);
      await shot(page, `${viewport.name}_08_cancelled`, "ui_shell", "none", "Cancellation is a cancelled job, not a completed plan.");

      api.mode.value = "treatment";
      api.counts.holdProcessing = false;
      api.counts.showEstimate = false;
      await page.getByRole("button", { name: "Generate Treatment Setup" }).click();
      await expect(page.getByRole("region", { name: "Smart Staging" })).toBeVisible({ timeout: 30_000 });
      const posts = api.counts.processing;
      const regenerates = api.counts.regenerate;
      await page.getByTestId("workflow-step-staging").click();
      await expect(page.getByRole("region", { name: "Smart Staging" })).toBeVisible();
      expect(api.counts.processing).toBe(posts);
      expect(api.counts.regenerate).toBe(regenerates);
      await shot(page, `${viewport.name}_09_staging`, "fixture_test_only", "generated_fixture_crowns", "Opening staging did not regenerate stages.");

      await page.getByTestId("staging-regenerate").click();
      await expect.poll(() => api.counts.regenerate).toBe(regenerates + 1);
      expect(api.counts.processing).toBe(posts);
      await shot(page, `${viewport.name}_10_staging_regenerate`, "fixture_test_only", "generated_fixture_crowns", "Regeneration is an explicit request.");

      await page.getByTestId("workflow-step-validation").click();
      await expect(page.getByTestId("validation-review-note")).toContainText(/not a pass/i);
      await shot(page, `${viewport.name}_11_validation`, "fixture_test_only", "generated_fixture_crowns", "Validation review. A missing check is not a pass.");

      await page.getByRole("button", { name: "Production" }).click();
      await expect(page.getByTestId("production-manufacturing-limit")).toContainText(/not manufacturing readiness/i);
      await shot(page, `${viewport.name}_12_production`, "unavailable", "generated_fixture_crowns", "Production does not claim manufacturing readiness.");

      await page.getByRole("button", { name: "Case Intake" }).click();
      await page.goBack();
      await expect(page.getByTestId("production-panel")).toBeVisible();
      await page.goForward();
      await expect(page.getByTestId("case-intake-panel")).toBeVisible();
      await shot(page, `${viewport.name}_13_back_forward`, "fixture_test_only", "generated_fixture_crowns", "Back and forward restore steps without a new run.");

      await page.getByTestId("workflow-step-production").click();
      await page.waitForFunction(() => sessionStorage.getItem("alignerstudio.activeWorkspace") === "production");
      await page.reload();
      await expect(page.getByTestId("production-panel")).toBeVisible({ timeout: 15_000 });
      await shot(page, `${viewport.name}_14_refresh_completed`, "fixture_test_only", "generated_fixture_crowns", "Refresh after completion restores the production step.");

      api.mode.value = "failed";
      await page.evaluate(() => sessionStorage.clear());
      await page.goto(WEB);
      await importScans(page);
      await page.getByRole("button", { name: "Analysis" }).click();
      const failedPosts = api.counts.pipeline;
      await page.getByRole("button", { name: "Analysis" }).click();
      expect(api.counts.pipeline).toBe(failedPosts);
      await page.getByTestId("analysis-panel").getByRole("button", { name: "Review segmentation" }).click();
      await expect(page.getByTestId("segmentation-review-strip")).toHaveAttribute("data-segmentation-kind", "failed", { timeout: 20_000 });
      await shot(page, `${viewport.name}_16_failure`, "failure", "none", "Failed segmentation stays failed. Opening the step is not a retry.");
      await assertShell(page);
    });
  }
});
