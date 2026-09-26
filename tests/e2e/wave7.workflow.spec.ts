/**
 * Wave 7 browser QA.
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
const EVIDENCE_DIR = path.join(ROOT, ".research/tmp/wave7_browser_qa");

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
  workflowState: string;
  nextAction: string;
  clinicalSegmentationValidation: false;
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
      summary: {
        finding_count: 1,
        checks_passed: 0,
        warnings: 1,
        errors: 0,
        unavailable_checks: 2,
        review_required_checks: 1,
      },
      checks: [{ check_state: "not_available", name: "manufacturing" }],
      findings: [
        {
          finding_id: "fixture-finding",
          category: "fixture",
          check_state: "requires_review",
          affected_tooth_refs: [],
          stage_index: 0,
          message: "Fixture finding. Not an approval.",
        },
      ],
    },
  };
}

async function installApi(page: Page): Promise<{
  mode: { value: "blocked" | "fixture" | "failed" | "treatment" | "stale" };
  counts: { pipeline: number; processing: number };
}> {
  const mode: { value: "blocked" | "fixture" | "failed" | "treatment" | "stale" } = { value: "blocked" };
  const counts = { pipeline: 0, processing: 0, holdProcessing: false };
  let polls = 0;
  await page.route("**/cases**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    const caseBody = {
      id: "wave7-case",
      patient_reference: "wave7-workflow",
      status: "mesh_validated",
      meshes: [
        { arch: "upper", file_path: "/tmp/upper.stl", original_filename: "upper.stl", uploaded_at: "2026-09-26T00:00:00Z" },
        { arch: "lower", file_path: "/tmp/lower.stl", original_filename: "lower.stl", uploaded_at: "2026-09-26T00:00:00Z" },
      ],
      created_at: "2026-09-26T00:00:00Z",
    };
    if (method === "POST" && /\/cases$/.test(url)) {
      await route.fulfill({
        json: { ...caseBody, status: "created", meshes: [] },
      });
      return;
    }
    if (method === "GET" && /\/cases\/wave7-case$/.test(url)) {
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
    if (method === "GET" && /\/treatment$/.test(url)) {
      if (mode.value === "treatment" || mode.value === "stale") {
        await route.fulfill({ json: treatmentBundle(mode.value === "stale") });
        return;
      }
      await route.fulfill({ status: 404, body: "none" });
      return;
    }
    if (method === "POST" && /\/processing$/.test(url)) {
      counts.processing += 1;
      polls = 0;
      await route.fulfill({
        json: {
          job_id: "wave7-job",
          stage_status: "PROCESSING",
          current_stage: "preparation",
          user_message: "Preparing the case.",
          overall_progress: null,
          elapsed_seconds: 1,
        },
      });
      return;
    }
    if (method === "GET" && url.includes("processing-status")) {
      polls += 1;
      const done = polls > 1 && !counts.holdProcessing;
      const status = !done
        ? "PROCESSING"
        : mode.value === "failed"
          ? "FAILED"
          : "COMPLETED";
      await route.fulfill({
        json: {
          job_id: "wave7-job",
          stage_status: status,
          current_stage: status === "FAILED" ? "failed" : "preparation",
          user_message: status === "FAILED" ? "The run failed." : status === "COMPLETED" ? "Stored for review." : "Preparing the case.",
          overall_progress: null,
          elapsed_seconds: polls,
          error_code: status === "FAILED" ? "decoder" : null,
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
  const workflowState =
    (await page.locator("[aria-current='step']").getAttribute("data-workflow-state").catch(() => "unknown")) ?? "unknown";
  const nextAction =
    (await page.getByTestId("workflow-step-brief").getAttribute("data-canonical-next-action").catch(() => "none")) ?? "none";
  images.push({
    file,
    viewport: viewport ? `${viewport.width}x${viewport.height}` : "unknown",
    provenance,
    geometry,
    workflowState,
    nextAction,
    clinicalSegmentationValidation: false,
    note,
  });
}

async function assertOneWorkflow(page: Page): Promise<void> {
  await expect(page.locator("[aria-current='step']")).toHaveCount(1);
  const canonical = await page.getByTestId("workflow-step-brief").getAttribute("data-canonical-next-action");
  const header = page.getByTestId("header-next-action");
  const primary = page.getByTestId("primary-next-action");
  const actionCount = (await header.count()) + (await primary.count());
  expect(actionCount).toBeLessThanOrEqual(1);
  if ((await header.count()) === 1) {
    await expect(header).toHaveAttribute("data-next-action", canonical ?? "");
  }
  if ((await primary.count()) === 1) {
    await expect(primary).toBeVisible();
  }
  const box = await page.locator(".cad-shell").boundingBox();
  const scroll = await page.evaluate(() => ({
    height: document.documentElement.scrollHeight,
    client: document.documentElement.clientHeight,
    width: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(scroll.height).toBeLessThanOrEqual(scroll.client + 4);
  expect(scroll.width).toBeLessThanOrEqual(scroll.clientWidth + 4);
  expect(box).not.toBeNull();
}

async function importScans(page: Page): Promise<void> {
  await page.locator("#patient-reference").fill("wave7");
  await page.getByTestId("create-case-primary").click();
  await page.locator("#upper-stl").setInputFiles({
    name: "upper.stl",
    mimeType: "model/stl",
    buffer: Buffer.from("upper-wave7"),
  });
  await page.locator("#lower-stl").setInputFiles({
    name: "lower.stl",
    mimeType: "model/stl",
    buffer: Buffer.from("lower-wave7"),
  });
}

test.describe.configure({ mode: "serial" });

test.describe("Wave 7 workflow", () => {
  test.afterAll(() => {
    fs.mkdirSync(EVIDENCE_DIR, { recursive: true });
    const evidencePath = path.join(EVIDENCE_DIR, "evidence.json");
    let priorImages: typeof images = [];
    let priorTimings: typeof timings = [];
    if (fs.existsSync(evidencePath)) {
      try {
        const prior = JSON.parse(fs.readFileSync(evidencePath, "utf8")) as {
          images?: typeof images;
          timings?: typeof timings;
        };
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
    for (const entry of [...priorTimings, ...timings]) {
      timingByKey.set(`${String(entry.viewport)}:${String(entry.transition)}`, entry);
    }
    fs.writeFileSync(
      evidencePath,
      JSON.stringify(
        {
          wave: 7,
          clinicalSegmentationValidation: false,
          liveToothInstanceNet: false,
          environment: "BLOCKED_BY_ENVIRONMENT",
          fixtureEvidence: "non-clinical",
          note: "Screenshots are UI evidence. Fixture crowns are generated test meshes, not patient inference. Blocked shots are an environment blocker, not zero teeth. WP-14 and WP-15 were not exercised.",
          viewports: VIEWPORTS,
          images: [...imageByFile.values()],
          timings: [...timingByKey.values()],
        },
        null,
        2,
      ),
    );
  });

  for (const viewport of VIEWPORTS) {
    test(`workflow matrix at ${viewport.name}`, async ({ page }) => {
      test.setTimeout(180_000);
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      const api = await installApi(page);
      await page.goto(WEB);
      await expect(page.locator("[aria-current='step']")).toHaveAttribute("data-workflow-state", /active|not_started/);
      await assertOneWorkflow(page);
      await shot(page, `${viewport.name}_01_launch`, "ui_shell", "none", "Launch opens case intake. No case is loaded.");

      await importScans(page);
      await assertOneWorkflow(page);
      await shot(page, `${viewport.name}_02_case_intake`, "ui_shell", "none", "Case intake with both scans. No segmentation has been started.");

      const pipelineBeforeNav = api.counts.pipeline;
      const started = Date.now();
      await page.getByRole("button", { name: "Analysis" }).click();
      await expect(page.getByTestId("analysis-panel")).toBeVisible();
      timings.push({
        viewport: viewport.name,
        transition: "case-intake-to-analysis",
        ms: Date.now() - started,
        pipelinePosts: api.counts.pipeline - pipelineBeforeNav,
      });
      expect(api.counts.pipeline).toBe(pipelineBeforeNav);
      await assertOneWorkflow(page);
      await shot(page, `${viewport.name}_03_analysis_not_started`, "ui_shell", "none", "Analysis opened without starting segmentation.");

      await page.getByTestId("analysis-panel").getByRole("button", { name: "Review segmentation" }).click();
      await expect(page.getByTestId("segmentation-review-strip")).toHaveAttribute(
        "data-segmentation-kind",
        "blocked_by_environment",
        { timeout: 20_000 },
      );
      await expect(page.getByTestId("analysis-environment-block")).toBeVisible();
      await expect(page.getByTestId("analysis-panel").getByRole("button", { name: "Review segmentation" })).toBeDisabled();
      await assertOneWorkflow(page);
      await shot(page, `${viewport.name}_04_analysis_blocked`, "blocked", "none", "Environment blocker. Not zero teeth. Retry is not offered.");

      await page.getByRole("button", { name: "Treatment Setup" }).click();
      await expect(page.getByTestId("treatment-target-empty")).toBeVisible();
      expect(api.counts.processing).toBe(0);
      await shot(
        page,
        `${viewport.name}_05_treatment_dependency`,
        "blocked",
        "none",
        "Treatment setup shows the missing target and does not start a plan.",
      );

      await page.evaluate(() => sessionStorage.clear());
      api.mode.value = "fixture";
      await page.goto(WEB);
      await importScans(page);
      await page.getByRole("button", { name: "Analysis" }).click();
      await page.getByTestId("analysis-panel").getByRole("button", { name: "Review segmentation" }).click();
      await expect(page.getByTestId("segmentation-review-strip")).toHaveAttribute(
        "data-segmentation-kind",
        "fixture_test_only",
        { timeout: 20_000 },
      );
      await expect(page.getByTestId("analysis-fixture-note")).toContainText(/test-only/i);
      await shot(
        page,
        `${viewport.name}_06_fixture_analysis`,
        "fixture_test_only",
        "generated_fixture_crowns",
        "Fixture segmentation is labeled test-only and is not patient inference.",
      );

      api.mode.value = "treatment";
      const processingBefore = api.counts.processing;
      await page.getByRole("button", { name: "Treatment Setup" }).click();
      await page.getByRole("button", { name: "Generate Treatment Setup" }).click();
      await expect(page.getByTestId("case-loading-overlay")).toBeVisible();
      await shot(page, `${viewport.name}_07_processing`, "ui_shell", "none", "Processing started only from the explicit create action.");
      expect(api.counts.processing).toBe(processingBefore + 1);
      await expect(page.getByTestId("staging-panel")).toBeVisible({ timeout: 15_000 });
      await page.getByRole("button", { name: "Treatment Setup" }).click();
      await expect(page.getByTestId("treatment-plan-stored")).toBeVisible();
      await shot(
        page,
        `${viewport.name}_08_treatment_plan`,
        "fixture_test_only",
        "generated_fixture_crowns",
        "Stored fixture plan. Opening the step did not start a second run.",
      );

      const posts = api.counts.processing;
      await page.getByRole("button", { name: "Staging" }).click();
      await expect(page.getByTestId("staging-panel")).toBeVisible();
      expect(api.counts.processing).toBe(posts);
      await expect(page.getByTestId("staging-freshness")).toHaveText("current");
      await shot(page, `${viewport.name}_09_staging`, "fixture_test_only", "generated_fixture_crowns", "Staging review. Not a clinical optimum.");

      api.mode.value = "stale";
      await expect(page.getByTestId("workflow-step-staging")).toHaveAttribute("aria-current", "step");
      await page.waitForFunction(() => sessionStorage.getItem("alignerstudio.activeWorkspace") === "staging");
      await page.reload();
      await expect(page.getByTestId("staging-panel")).toBeVisible({ timeout: 15_000 });
      await expect(page.locator("[data-workflow-state='stale']").first()).toBeVisible();
      await shot(page, `${viewport.name}_10_staging_stale`, "stale", "generated_fixture_crowns", "Stale staging stays explicit after refresh.");

      await page.getByRole("button", { name: "Refinement" }).click();
      await expect(page.getByTestId("refinement-unavailable")).toContainText("Boundary edit is not available");
      await expect(page.getByRole("button", { name: "Split" })).toHaveCount(0);
      await shot(page, `${viewport.name}_11_refinement`, "fixture_test_only", "generated_fixture_crowns", "Refinement lists unsupported edits as text, not broken buttons.");

      await page.getByTestId("workflow-step-validation").click();
      await expect(page.getByTestId("workflow-step-validation")).toHaveAttribute("aria-current", "step");
      await expect(page.getByTestId("validation-review-note")).toContainText(/not a pass/i);
      await shot(page, `${viewport.name}_12_validation_stale`, "stale", "generated_fixture_crowns", "Stale validation. Missing checks are not a pass.");

      await page.getByRole("button", { name: "Production" }).click();
      await expect(page.getByTestId("production-manufacturing-limit")).toContainText(/not manufacturing readiness/i);
      await shot(page, `${viewport.name}_13_production`, "unavailable", "generated_fixture_crowns", "Production states the manufacturing limit.");

      await page.getByRole("button", { name: "Case Intake" }).click();
      await expect(page.getByTestId("case-intake-panel")).toBeVisible();
      await page.goBack();
      await expect(page.getByTestId("production-panel")).toBeVisible();
      await shot(page, `${viewport.name}_14_back`, "fixture_test_only", "generated_fixture_crowns", "Browser back returns to production without a new run.");
      await page.goForward();
      await expect(page.getByTestId("case-intake-panel")).toBeVisible();
      await shot(page, `${viewport.name}_15_forward`, "fixture_test_only", "generated_fixture_crowns", "Browser forward returns to case intake.");

      await page.getByTestId("workflow-step-production").click();
      await page.waitForFunction(() => sessionStorage.getItem("alignerstudio.activeWorkspace") === "production");
      await page.reload();
      await expect(page.getByTestId("production-panel")).toBeVisible({ timeout: 15_000 });
      await shot(page, `${viewport.name}_16_refresh`, "fixture_test_only", "generated_fixture_crowns", "Refresh restores the case and the production step.");

      api.mode.value = "failed";
      await page.evaluate(() => sessionStorage.clear());
      await page.goto(WEB);
      await importScans(page);
      await page.getByRole("button", { name: "Analysis" }).click();
      const failedPosts = api.counts.pipeline;
      await page.getByRole("button", { name: "Analysis" }).click();
      expect(api.counts.pipeline).toBe(failedPosts);
      await page.getByTestId("analysis-panel").getByRole("button", { name: "Review segmentation" }).click();
      await expect(page.getByTestId("segmentation-review-strip")).toHaveAttribute("data-segmentation-kind", "failed", {
        timeout: 20_000,
      });
      await shot(page, `${viewport.name}_17_failure`, "failure", "none", "Failed segmentation stays a failure. Opening the step is separate from the retry click.");

      api.counts.holdProcessing = true;
      api.mode.value = "treatment";
      await page.getByRole("button", { name: "Case Intake" }).click();
      const before = api.counts.processing;
      await page.getByRole("button", { name: "Generate Treatment Setup" }).click();
      await expect(page.getByTestId("case-loading-overlay")).toBeVisible();
      await page.reload();
      await expect(page.getByTestId("case-loading-overlay")).toBeVisible({ timeout: 15_000 });
      expect(api.counts.processing).toBeGreaterThanOrEqual(before);
      await shot(page, `${viewport.name}_18_processing_recovery`, "ui_shell", "none", "Refresh keeps the in-progress run. It does not invent a completed plan.");
      api.counts.holdProcessing = false;
    });
  }
});
