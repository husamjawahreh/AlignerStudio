/**
 * Wave 9 browser QA. Fixture crowns are test meshes, not patient inference.
 * Requires the web app at P8_WEB_URL (default http://127.0.0.1:5173).
 */
import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEB = process.env.P8_WEB_URL ?? "http://127.0.0.1:5173";
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const EVIDENCE_DIR = path.join(ROOT, ".research/tmp/wave9_browser_qa");
const VIEWPORTS = [
  { width: 1366, height: 768, name: "1366x768" },
  { width: 1600, height: 1000, name: "1600x1000" },
  { width: 1280, height: 800, name: "1280x800" },
] as const;

const images: Array<Record<string, unknown>> = [];

function crown(arch: "upper" | "lower", index: number) {
  const cx = index * 3;
  const cy = arch === "upper" ? 6 : -6;
  const vertices = [[cx, cy, 0], [cx + 1, cy, 0], [cx, cy + 1, 0], [cx, cy, 1]];
  const faces = [[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]];
  return {
    instance_id: (arch === "upper" ? 0 : 20) + index,
    tooth_ref: `${arch}:instance:${index}`,
    fdi_number: null,
    arch,
    vertices,
    faces,
    centroid: [cx, cy, 0],
    confidence: null,
    provenance: "fixture",
    fixture: true,
    experimental: true,
    planning_mode: "semantic_only_experimental",
    identification_status: "uncertain",
  };
}

function movement() {
  return { translationX: 0, translationY: 0, translationZ: 0, rotation: 0, tip: 0, torque: 0, angulation: 0, intrusion: 0, extrusion: 0 };
}

function treatmentTooth(arch: "upper" | "lower", index: number) {
  const mesh = crown(arch, index);
  return {
    instanceId: mesh.instance_id,
    fdiNumber: null,
    toothRef: mesh.tooth_ref,
    planningMode: "semantic_only_experimental",
    arch,
    confidence: 0,
    vertices: mesh.vertices,
    faces: mesh.faces,
    centroid: mesh.centroid,
    identificationStatus: "uncertain",
    movement: movement(),
    validationStatus: "unavailable",
    validationMessage: "Fixture/test-only surface. Not a clinical finding.",
    provenance: "fixture",
    fixture: true,
    experimental: true,
    limitStatus: "not_configured",
  };
}

function treatmentBundle(stale: boolean) {
  const teeth = [0, 1].flatMap((index) => [treatmentTooth("upper", index), treatmentTooth("lower", index)]);
  const freshness = stale ? "stale" : "current";
  return {
    stages: [0, 1].map((index) => ({
      index,
      stageId: `fixture-stage-${index}`,
      teeth,
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
    iprSites: [{
      siteId: "ipr-1",
      toothA: "upper:instance:0",
      toothB: "upper:instance:1",
      status: "needs_review",
      measuredAmount: 1.2,
      currentDistance: 1.2,
      amountUnit: "model units",
      valueSource: "centroid_distance",
      truthState: "requires_review",
    }],
    attachmentSites: [{
      siteId: "att-1",
      tooth: "upper:instance:0",
      status: "needs_review",
      truthState: "requires_review",
      valueSource: "review_candidate",
    }],
    sourceKind: "development_treatment_fixture",
    unavailableReason: "Browser QA fixture. Not clinical evidence.",
    smartStaging: {
      freshness,
      stage_count: 2,
      clinically_approved: false,
      clinically_optimal: false,
      meta: { freshness, truth_state: freshness, clinically_approved: false, clinically_optimal: false },
    },
    validationCapability: {
      freshness,
      summary: { finding_count: 1, checks_passed: 0, warnings: 1, errors: 0, unavailable_checks: 2, review_required_checks: 1 },
      checks: [{ check_state: "not_available", name: "manufacturing" }],
      findings: [{ finding_id: "fixture-finding", category: "fixture", check_state: "requires_review", affected_tooth_refs: [], stage_index: 0, message: "Fixture finding. Not an approval." }],
    },
    clinicalTools: {
      freshness,
      readiness: { ipr_measurement: "requires_review", attachment_placement: "requires_review" },
      notes: ["Centroid distance is not an IPR prescription."],
    },
  };
}

async function installApi(page: Page) {
  const mode: { value: "blocked" | "fixture" | "treatment" | "stale" } = { value: "blocked" };
  const counts = { pipeline: 0, processing: 0, edits: 0, regenerate: 0 };
  let polls = 0;
  await page.route("**/cases**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    const caseBody = {
      id: "wave9-case",
      patient_reference: "wave9-depth",
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
    if (method === "GET" && /\/cases\/wave9-case$/.test(url)) {
      await route.fulfill({ json: caseBody });
      return;
    }
    if (method === "POST" && url.includes("/uploads") && !url.includes("validate")) {
      await route.fulfill({ json: caseBody });
      return;
    }
    if (method === "POST" && url.includes("/validate")) {
      await route.fulfill({ json: { is_valid: true, triangle_count: 4, is_watertight: true, errors: [] } });
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
      await route.fulfill({
        json: {
          state: "identification_incomplete",
          source_kind: "validated_real_case",
          tooth_instance_count: 2,
          identified_teeth: 0,
          uncertain_teeth: 2,
          unidentified_teeth: 2,
          validation_findings: [],
          failures: [],
          notes: ["fixture presentation crowns"],
          provenance: "fixture",
          fixture: true,
          experimental: true,
          tooth_instances: [0, 1].map((index) => crown(arch, index)),
        },
      });
      return;
    }
    if (method === "POST" && url.includes("/treatment/edits")) {
      counts.edits += 1;
      await route.fulfill({ json: treatmentBundle(mode.value === "stale") });
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
    if (method === "POST" && /\/processing$/.test(url)) {
      counts.processing += 1;
      polls = 0;
      await route.fulfill({
        json: {
          job_id: "wave9-job",
          stage_status: "PROCESSING",
          current_stage: "preparation",
          user_message: "Preparing the case.",
          overall_progress: null,
          elapsed_seconds: 1,
          remaining_time: { kind: "none", seconds: null, confidence: null, sample_count: 0, qualifier: "none", label: "No reliable remaining-time estimate" },
        },
      });
      return;
    }
    if (method === "GET" && url.includes("processing-status")) {
      polls += 1;
      const done = polls > 1;
      await route.fulfill({
        json: {
          job_id: "wave9-job",
          stage_status: done ? "COMPLETED" : "PROCESSING",
          current_stage: "preparation",
          user_message: done ? "Stored for review." : "Preparing the case.",
          overall_progress: null,
          elapsed_seconds: polls,
          remaining_time: { kind: "none", seconds: null, confidence: null, sample_count: 0, qualifier: "none", label: "No reliable remaining-time estimate" },
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

async function shot(page: Page, name: string, note: string) {
  fs.mkdirSync(EVIDENCE_DIR, { recursive: true });
  await page.screenshot({ path: path.join(EVIDENCE_DIR, `${name}.png`), fullPage: false });
  images.push({ file: `${name}.png`, viewport: page.viewportSize(), note, clinicalSegmentationValidation: false });
}

async function importScans(page: Page) {
  await page.locator("#patient-reference").fill("wave9");
  await page.getByTestId("create-case-primary").click();
  await page.locator("#upper-stl").setInputFiles({ name: "upper.stl", mimeType: "model/stl", buffer: Buffer.from("upper-wave9") });
  await page.locator("#lower-stl").setInputFiles({ name: "lower.stl", mimeType: "model/stl", buffer: Buffer.from("lower-wave9") });
}

test.describe.configure({ mode: "serial" });

test.describe("Wave 9 feature depth", () => {
  test.afterAll(() => {
    fs.mkdirSync(EVIDENCE_DIR, { recursive: true });
    const evidencePath = path.join(EVIDENCE_DIR, "evidence.json");
    let prior: Array<Record<string, unknown>> = [];
    if (fs.existsSync(evidencePath)) {
      try {
        prior = (JSON.parse(fs.readFileSync(evidencePath, "utf8")) as { images?: Array<Record<string, unknown>> }).images ?? [];
      } catch {
        prior = [];
      }
    }
    const byFile = new Map<string, Record<string, unknown>>();
    for (const image of [...prior, ...images]) byFile.set(String(image.file), image);
    fs.writeFileSync(evidencePath, JSON.stringify({
      wave: 9,
      firstVersionAcceptance: false,
      liveToothInstanceNet: false,
      environment: "BLOCKED_BY_ENVIRONMENT",
      fixtureEvidence: "non-clinical",
      note: "Screenshots are UI evidence. Fixture crowns are generated test meshes. WP-14 and WP-15 were not exercised.",
      viewports: VIEWPORTS,
      images: [...byFile.values()],
    }, null, 2));
  });

  for (const viewport of VIEWPORTS) {
    test(`feature depth at ${viewport.name}`, async ({ page }) => {
      test.setTimeout(180_000);
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      const api = await installApi(page);
      await page.goto(WEB);
      await importScans(page);
      await page.getByRole("button", { name: "Analysis", exact: true }).click();
      await expect(page.getByTestId("analysis-panel")).toBeVisible();
      const before = api.counts.pipeline;
      await page.getByRole("button", { name: "Analysis", exact: true }).click();
      expect(api.counts.pipeline).toBe(before);
      await shot(page, `${viewport.name}_01_analysis`, "Analysis opened without a segmentation run.");

      await page.getByTestId("analysis-panel").getByRole("button", { name: "Review segmentation" }).click();
      await expect(page.getByTestId("analysis-environment-block")).toBeVisible({ timeout: 20_000 });
      await shot(page, `${viewport.name}_02_analysis_blocked`, "Environment blocker. Not zero teeth.");

      await page.evaluate(() => sessionStorage.clear());
      api.mode.value = "fixture";
      await page.goto(WEB);
      await importScans(page);
      await page.getByRole("button", { name: "Analysis", exact: true }).click();
      await page.getByTestId("analysis-panel").getByRole("button", { name: "Review segmentation" }).click();
      await expect(page.getByTestId("analysis-fixture-note")).toContainText(/test-only/i, { timeout: 20_000 });

      api.mode.value = "treatment";
      await page.getByRole("button", { name: "Treatment Setup", exact: true }).click();
      await page.getByRole("button", { name: "Generate Treatment Setup" }).click();
      await expect(page.getByRole("region", { name: "Smart Staging" })).toBeVisible({ timeout: 20_000 });
      await page.getByRole("button", { name: "Treatment Setup", exact: true }).click();
      await expect(page.getByTestId("setup-no-movement-limits")).toBeVisible();
      await expect(page.getByTestId("inspection-panel")).toBeVisible();
      await shot(page, `${viewport.name}_03_treatment_setup`, "Stored plan. No movement limits. Numeric inspector is present.");

      await page.getByTestId("dental-map-upper:instance:0").click();
      await expect(page.getByTestId("contextual-tooth-toolbar")).toBeVisible();
      await expect(page.getByTestId("inspection-tooth-ref")).toContainText("upper:instance:0");
      await shot(page, `${viewport.name}_04_one_tooth`, "One fixture tooth. Identity is the tooth reference, not an invented number.");

      await page.getByTestId("dental-map-upper:instance:1").click({ modifiers: ["Shift"] });
      await expect(page.getByTestId("dental-map-upper:instance:1")).toHaveAttribute("aria-selected", "true");
      await shot(page, `${viewport.name}_05_multi_tooth`, "Shift adds a second fixture tooth.");

      await page.getByTestId("dental-map-upper:instance:0").click();
      const spin = page.getByTestId("inspection-panel").getByRole("spinbutton").first();
      await spin.fill("0.4");
      await expect(page.getByRole("button", { name: "Apply" })).toBeEnabled();
      const edits = api.counts.edits;
      await page.getByRole("button", { name: "Apply" }).click();
      await expect.poll(() => api.counts.edits).toBe(edits + 1);
      await page.getByRole("button", { name: "Undo doctor edit" }).click();
      await expect.poll(() => api.counts.edits).toBe(edits + 2);
      await shot(page, `${viewport.name}_06_edit_undo`, "Numeric edit and undo use the existing edit request. Not a new engine.");

      const regenerates = api.counts.regenerate;
      await page.getByTestId("workflow-step-staging").click();
      await expect(page.getByTestId("staging-not-optimal")).toBeVisible();
      expect(api.counts.regenerate).toBe(regenerates);
      await page.getByTestId("staging-regenerate").click();
      await expect.poll(() => api.counts.regenerate).toBe(regenerates + 1);
      await shot(page, `${viewport.name}_07_staging`, "Opening staging did not regenerate. Regeneration was explicit. Not clinically optimal.");

      api.mode.value = "stale";
      await page.waitForFunction(() => sessionStorage.getItem("alignerstudio.activeWorkspace") === "staging");
      await page.reload();
      await expect(page.getByTestId("staging-freshness")).toHaveText("stale", { timeout: 15_000 });
      await shot(page, `${viewport.name}_08_staging_stale`, "Stale staging stays stale after refresh.");

      await page.getByRole("button", { name: "Refinement", exact: true }).click();
      await expect(page.getByTestId("refinement-unavailable")).toContainText("Boundary edit is not available");
      await expect(page.getByRole("button", { name: "Split" })).toHaveCount(0);
      await shot(page, `${viewport.name}_09_refinement`, "Unsupported edits are text, not broken buttons.");

      await page.getByTestId("workflow-step-validation").click();
      await expect(page.getByTestId("validation-review-note")).toContainText(/not a pass/i);
      await shot(page, `${viewport.name}_10_validation`, "Validation review. A missing check is not a pass.");

      await page.getByRole("button", { name: "Production", exact: true }).click();
      await expect(page.getByTestId("production-manufacturing-limit")).toContainText(/not manufacturing readiness/i);
      await shot(page, `${viewport.name}_11_production`, "Production does not claim manufacturing certification.");
    });
  }
});
