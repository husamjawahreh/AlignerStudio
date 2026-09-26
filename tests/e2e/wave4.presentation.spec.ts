/**
 * Wave 4 browser QA.
 *
 * Presentation evidence only. Fixture crowns and blocked states are not
 * clinical segmentation validation and are not live ToothInstanceNet output.
 *
 * Requires the web app at P8_WEB_URL (default http://127.0.0.1:5173).
 */
import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEB = process.env.P8_WEB_URL ?? "http://127.0.0.1:5173";
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const EVIDENCE_DIR = path.join(ROOT, ".research/tmp/wave4_browser_qa");

const VIEWPORTS = [
  { width: 1366, height: 768, name: "1366x768" },
  { width: 1600, height: 1000, name: "1600x1000" },
] as const;

type Provenance = "ui_shell" | "blocked" | "fixture_test_only";

const images: Array<{
  file: string;
  viewport: string;
  provenance: Provenance;
  geometry: string;
  clinicalSegmentationValidation: false;
  note: string;
}> = [];

const performanceNotes: Array<{ viewport: string; action: string; milliseconds: number }> = [];

function crown(arch: "upper" | "lower", index: number) {
  const span = 6;
  const t = index / (span - 1);
  const angle = (t - 0.5) * 1.15;
  const arc = 18;
  const cx = Math.sin(angle) * arc;
  const cz = (Math.cos(angle) - 1) * arc * 0.7;
  const cy = arch === "upper" ? 7 : -7;
  const vertices: number[][] = [];
  const faces: number[][] = [];
  const segments = 10;
  const rings = 6;
  for (let ring = 0; ring <= rings; ring += 1) {
    const v = ring / rings;
    const y = (v - 0.35) * 5.2;
    const radius = 0.55 + Math.sin(Math.PI * v) * 1.15;
    for (let segment = 0; segment < segments; segment += 1) {
      const theta = (segment / segments) * Math.PI * 2;
      vertices.push([
        cx + Math.cos(theta) * radius * 0.82,
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
  await page.route("**/cases**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    if (method === "POST" && /\/cases$/.test(url)) {
      await route.fulfill({
        json: {
          id: "wave4-case",
          patient_reference: "wave4-presentation",
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
          id: "wave4-case",
          patient_reference: "wave4-presentation",
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
          tooth_instance_count: 6,
          identification_confidence: null,
          identified_teeth: 0,
          uncertain_teeth: 6,
          unidentified_teeth: 6,
          validation_findings: [],
          failures: [],
          arch_analysis_available: false,
          notes: ["fixture presentation crowns"],
          provenance: "fixture",
          fixture: true,
          experimental: true,
          tooth_instances: Array.from({ length: 6 }, (_, index) => crown(arch, index)),
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

async function openCase(page: Page, reference: string): Promise<void> {
  await page.locator("#patient-reference").fill(reference);
  await page.getByTestId("create-case-primary").click();
  await page.locator("#upper-stl").setInputFiles({
    name: "upper.stl",
    mimeType: "model/stl",
    buffer: Buffer.from("upper-presentation"),
  });
  await page.locator("#lower-stl").setInputFiles({
    name: "lower.stl",
    mimeType: "model/stl",
    buffer: Buffer.from("lower-presentation"),
  });
  await page.getByRole("button", { name: "Review segmentation" }).click();
}

async function settle(page: Page): Promise<void> {
  await page.waitForTimeout(520);
}

test.describe.configure({ mode: "serial" });

test.describe("Wave 4 premium 3D presentation", () => {
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
          wave: 4,
          clinicalSegmentationValidation: false,
          liveToothInstanceNet: false,
          note: "Screenshots are presentation evidence. Fixture crowns are generated test meshes. Blocked shots are not a tooth count of zero. No patient STL was loaded.",
          images,
          performance: performanceNotes,
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
      await shot(page, `${viewport.name}_01_launch`, "ui_shell", "none", "Application launch. No case geometry.");
      await assertNoPageOverflow(page);

      await page.locator("#patient-reference").fill("wave4-blocked");
      await page.getByTestId("create-case-primary").click();
      await expect(page.getByTestId("case-intake-panel")).toHaveAttribute("data-case-state", "active");
      await shot(page, `${viewport.name}_02_case_intake`, "ui_shell", "none", "Case intake before segmentation.");

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
      await expect(page.locator("canvas")).toHaveCount(0);
      await shot(
        page,
        `${viewport.name}_03_blocked_segmentation`,
        "blocked",
        "none",
        "Live inference blocked. The viewport does not invent an empty tooth scene.",
      );
      await assertNoPageOverflow(page);
      const viewportBox = await page.getByTestId("layout-viewport").boundingBox();
      const inspector = await page.getByTestId("adaptive-inspector").boundingBox();
      expect(viewportBox && inspector && viewportBox.width > inspector.width).toBeTruthy();
    });

    test(`fixture presentation views at ${viewport.name}`, async ({ page }) => {
      test.setTimeout(180_000);
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await installApi(page, "fixture");
      await page.goto(WEB);
      await openCase(page, `wave4-fixture-${viewport.name}`);
      await expect(page.getByTestId("segmentation-review-strip")).toHaveAttribute(
        "data-segmentation-kind",
        "fixture_test_only",
      );
      await expect(page.getByTestId("segmentation-provenance")).toHaveText("Fixture / test-only");
      await expect(page.locator("canvas")).toBeVisible();
      await settle(page);
      await shot(
        page,
        `${viewport.name}_04_both_arches`,
        "fixture_test_only",
        "generated_fixture_crowns",
        "Both arches. Default labels are selected-only, so unlabeled teeth stay clear.",
      );

      await page.getByTestId("tool-labels").click();
      await page.getByTestId("tool-labels").click();
      await expect(page.getByTestId("tool-labels")).toHaveText("Labels: all");
      await settle(page);
      await shot(
        page,
        `${viewport.name}_05_labels_all`,
        "fixture_test_only",
        "generated_fixture_crowns",
        "All-label mode. Text is tooth_ref. FDI is not shown on fixture identity.",
      );
      await expect(page.locator(".stage-tooth-label").first()).toBeVisible();
      await expect(page.locator(".stage-tooth-label.is-unresolved").first()).toBeVisible();
      const labelText = await page.locator(".stage-tooth-label").first().innerText();
      expect(labelText).not.toMatch(/FDI/);

      const archStart = Date.now();
      await page.getByTestId("tool-arch-upper").click();
      await expect(page.getByTestId("tool-arch-upper")).toHaveClass(/is-active/);
      await page.getByTestId("tool-fit-arch").click();
      await settle(page);
      performanceNotes.push({
        viewport: viewport.name,
        action: "arch-upper-toggle-plus-frame",
        milliseconds: Date.now() - archStart,
      });
      await shot(page, `${viewport.name}_06_upper_only`, "fixture_test_only", "generated_fixture_crowns", "Upper arch only.");

      await page.getByTestId("tool-arch-lower").click();
      await page.getByTestId("tool-fit-arch").click();
      await settle(page);
      await shot(page, `${viewport.name}_07_lower_only`, "fixture_test_only", "generated_fixture_crowns", "Lower arch only.");

      await page.getByTestId("tool-arch-both").click();
      await page.getByTestId("tool-fit-case").click();
      await settle(page);
      await page.getByTestId("dental-map-upper:instance:0").click();
      await expect(page.getByTestId("selection-count")).toHaveText("1 selected");
      await expect(page.getByTestId("dental-map-upper:instance:0")).toHaveAttribute("aria-selected", "true");
      await settle(page);
      await shot(
        page,
        `${viewport.name}_08_selected_tooth`,
        "fixture_test_only",
        "generated_fixture_crowns",
        "One selected tooth_ref. Ordinary selection does not retarget the camera.",
      );

      await page.getByTestId("dental-map-lower:instance:1").click({ modifiers: ["Shift"] });
      await expect(page.getByTestId("selection-count")).toHaveText("2 selected");
      await settle(page);
      await shot(
        page,
        `${viewport.name}_09_multi_selection`,
        "fixture_test_only",
        "generated_fixture_crowns",
        "Multi-selection stays on tooth_ref and stays in sync with the dental map.",
      );

      await page.getByTestId("tool-view-occlusal").click();
      await settle(page);
      await shot(page, `${viewport.name}_10_occlusal`, "fixture_test_only", "generated_fixture_crowns", "Occlusal preset.");

      await page.getByTestId("tool-view-front").click();
      await settle(page);
      await shot(page, `${viewport.name}_11_frontal`, "fixture_test_only", "generated_fixture_crowns", "Frontal preset.");

      await page.getByTestId("tool-view-lateral").click();
      await settle(page);
      await shot(page, `${viewport.name}_12_lateral`, "fixture_test_only", "generated_fixture_crowns", "Right lateral preset.");

      await page.getByTestId("tool-fit-selection").click();
      await settle(page);
      await shot(
        page,
        `${viewport.name}_13_fit_selection`,
        "fixture_test_only",
        "generated_fixture_crowns",
        "Explicit fit-selection. This is a camera command, not ordinary selection.",
      );

      await page.getByTestId("toolbar-unavailable").evaluate((element) => {
        if (element instanceof HTMLDetailsElement) element.open = true;
      });
      await expect(page.getByTestId("toolbar-unavailable")).toContainText("No treatment target is stored", {
        timeout: 5000,
      });
      await expect(page.getByTestId("toolbar-unavailable")).toContainText("Distances are not invented");
      await shot(
        page,
        `${viewport.name}_14_current_target_unavailable`,
        "fixture_test_only",
        "generated_fixture_crowns",
        "No stored treatment target, so current/target comparison is not drawn.",
      );

      const validationNav = page.getByRole("button", { name: /Validation/ });
      await expect(validationNav).toHaveAttribute("title", /treatment plan is required/i);
      await shot(
        page,
        `${viewport.name}_15_validation_unavailable`,
        "fixture_test_only",
        "generated_fixture_crowns",
        "Validation step is blocked without a treatment plan. No validation overlay is drawn.",
      );
      await assertNoPageOverflow(page);

      const viewportBox = await page.getByTestId("layout-viewport").boundingBox();
      const inspector = await page.getByTestId("adaptive-inspector").boundingBox();
      const toolbar = await page.locator(".contextual-workspace-toolbar").boundingBox();
      expect(viewportBox && inspector && viewportBox.width > inspector.width).toBeTruthy();
      expect(viewportBox && toolbar && toolbar.y >= (viewportBox.y - 2)).toBeTruthy();
      const frame = await page.evaluate(() => {
        const start = performance.now();
        return new Promise<number>((resolve) => {
          requestAnimationFrame(() => {
            requestAnimationFrame(() => resolve(performance.now() - start));
          });
        });
      });
      performanceNotes.push({ viewport: viewport.name, action: "two-animation-frames", milliseconds: frame });
    });
  }
});
