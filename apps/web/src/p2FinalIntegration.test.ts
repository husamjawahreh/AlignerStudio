import { describe, expect, it } from "vitest";
import { WORKFLOW_DEFINITIONS, buildWorkflowActions } from "./workflow";
import {
  buildProductionNavigation,
  buildRefinementNavigation,
  buildValidationNavigation,
} from "./workflowNavigationPresentation";
import { engineeringFixtureBundle } from "./review/fixtureData";

/**
 * P2 Final Integration QA — terminology and navigation contract vs Master Plan v2.1.
 * Presentation/navigation only; does not exercise treatment-math or export engines.
 */
describe("P2 Final Integration QA", () => {
  it("keeps a single seven-step Master Plan workflow order", () => {
    expect(WORKFLOW_DEFINITIONS.map((step) => step.label)).toEqual([
      "Case Intake",
      "Analysis",
      "Treatment Setup",
      "Staging",
      "Refinement",
      "Validation",
      "Production",
    ]);
  });

  it("uses doctor-facing Treatment Setup / Production CTAs", () => {
    const setup = buildWorkflowActions({
      activeStep: "treatment-setup",
      hasCase: true,
      bothArchesValid: true,
      hasSegmentation: true,
      hasTreatment: false,
      isBusy: false,
    });
    expect(setup.map((action) => action.label)).toContain("Review Treatment Setup");
    expect(setup.every((action) => !/proposal|Generate Plan$/i.test(action.label))).toBe(true);

    const production = buildWorkflowActions({
      activeStep: "production",
      hasCase: true,
      bothArchesValid: true,
      hasSegmentation: true,
      hasTreatment: true,
      isBusy: false,
    });
    expect(production.map((action) => action.label)).toContain("Export Package");
  });

  it("exposes Refinement / Validation / Production navigation labels without inventing capabilities", () => {
    expect(buildRefinementNavigation(engineeringFixtureBundle).map((row) => row.label)).toEqual([
      "Tooth Controls",
      "Movement",
      "Attachments",
      "IPR",
      "Edit History",
    ]);
    expect(
      buildValidationNavigation(engineeringFixtureBundle, null).map((row) => row.label),
    ).toEqual([
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
    const production = buildProductionNavigation(engineeringFixtureBundle);
    expect(production.map((row) => row.label)).toEqual([
      "Appliance Stages",
      "Manufacturing Preparation",
      "IPR Report",
      "Attachment Plan",
      "Auxiliary Features",
      "Export Package",
      "Production QA",
    ]);
    expect(production.find((row) => row.id === "auxiliary-features")?.value).toBe("unavailable");
  });
});
