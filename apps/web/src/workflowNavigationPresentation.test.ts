import { describe, expect, it } from "vitest";
import { engineeringFixtureBundle } from "./review/fixtureData";
import type { ReviewBundle } from "./review/types";
import {
  buildProductionNavigation,
  buildRefinementNavigation,
  buildValidationNavigation,
} from "./workflowNavigationPresentation";

describe("Workflow navigation presentation", () => {
  it("exposes Refinement navigation labels without inventing edit capabilities", () => {
    const rows = buildRefinementNavigation(engineeringFixtureBundle);
    expect(rows.map((row) => row.label)).toEqual([
      "Tooth Controls",
      "Movement",
      "Attachments",
      "IPR",
      "Edit History",
    ]);
    expect(rows.find((row) => row.id === "attachments")?.value).toBe(
      String(engineeringFixtureBundle.attachmentSites.length),
    );
  });

  it("exposes Validation navigation labels and falls back to Unavailable", () => {
    const empty: ReviewBundle = {
      ...engineeringFixtureBundle,
      stages: [],
      validationSummary: undefined,
    };
    const unavailable = buildValidationNavigation(empty, null);
    expect(unavailable.map((row) => row.label)).toEqual([
      "Geometry",
      "Contacts",
      "Proximity",
      "Collisions",
      "Movement Constraints",
      "Stage Consistency",
      "Data Completeness",
      "Provenance",
      "Review Status",
    ]);
    expect(unavailable.every((row) => row.value === "Unavailable")).toBe(true);

    const withStage = buildValidationNavigation(
      engineeringFixtureBundle,
      engineeringFixtureBundle.stages[2],
    );
    expect(withStage.find((row) => row.id === "proximity")?.value).toBe("1");
    expect(withStage.find((row) => row.id === "reviewStatus")?.value).toBe("required");
  });

  it("reads Validation summary values when present", () => {
    const bundle: ReviewBundle = {
      ...engineeringFixtureBundle,
      validationSummary: {
        geometry: "computed",
        contacts: "computed",
        proximity: "computed",
        collisions: "computed",
        movementConstraints: "unavailable",
        stageConsistency: "computed",
        dataCompleteness: "warning",
        provenance: "computed",
        doctorReview: "required",
        findings: [],
      },
    };
    const rows = buildValidationNavigation(bundle, bundle.stages[0]);
    expect(rows.find((row) => row.id === "movementConstraints")?.value).toBe("unavailable");
    expect(rows.find((row) => row.id === "reviewStatus")?.value).toBe("required");
    expect(rows.find((row) => row.id === "dataCompleteness")?.value).toBe("warning");
  });

  it("exposes Production navigation labels without inventing manufacturing features", () => {
    const rows = buildProductionNavigation(engineeringFixtureBundle);
    expect(rows.map((row) => row.label)).toEqual([
      "Appliance Stages",
      "Manufacturing Preparation",
      "IPR Report",
      "Attachment Plan",
      "Auxiliary Features",
      "Export Package",
      "Production QA",
    ]);
    expect(rows.find((row) => row.id === "auxiliary-features")?.value).toBe("unavailable");
    expect(rows.find((row) => row.id === "export-package")?.value).toBe("Incomplete");
    expect(rows.find((row) => row.id === "manufacturing-preparation")?.value).toBe("unavailable");
    expect(rows.find((row) => row.id === "production-qa")?.value).toBe("unavailable");
    expect(rows.find((row) => row.id === "appliance-stages")?.value).toBe(
      String(engineeringFixtureBundle.stages.length),
    );
  });
});
