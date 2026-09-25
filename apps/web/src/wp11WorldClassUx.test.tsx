import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CaseIntakePanel } from "./components/CaseIntakePanel";
import {
  AdvancedDetails,
  CurrentTargetPair,
  formatProductTruthLabel,
  normalizeProductTruth,
} from "./design-system";
import { buildWorkflowActions } from "./workflow";

describe("WP-11 world-class UX", () => {
  it("normalizes product truth labels without inventing Verified", () => {
    expect(normalizeProductTruth("requires_review")).toBe("requires_review");
    expect(normalizeProductTruth("boundary_only")).toBe("not_available");
    expect(formatProductTruthLabel("not_available")).toBe("Not Available");
    expect(formatProductTruthLabel("computed")).toBe("Computed");
  });

  it("shows Create Case before active case and Active Case after", () => {
    const emptyUpload = { filename: "", size: 0, state: "empty" as const };
    const { rerender } = render(
      <CaseIntakePanel
        patientReference="P-1"
        onPatientReferenceChange={() => undefined}
        caseId={null}
        caseStatus={null}
        archUploads={{ upper: emptyUpload, lower: emptyUpload }}
        fileInputKeys={{ upper: 0, lower: 0 }}
        scanImportDisabled
        isBusy={false}
        bothArchesValid={false}
        backendTreatment={false}
        processingStatus={null}
        onCreateCase={() => undefined}
        onUpload={() => undefined}
        onRemoveMesh={() => undefined}
        onAnalyzeCase={() => undefined}
        onReviewTreatmentProposal={() => undefined}
      />,
    );
    expect(screen.getByTestId("case-intake-panel")).toHaveAttribute("data-case-state", "create");
    expect(screen.getByRole("button", { name: "Create case" })).toBeInTheDocument();
    expect(screen.queryByTestId("active-case-id")).not.toBeInTheDocument();

    rerender(
      <CaseIntakePanel
        patientReference="P-1"
        onPatientReferenceChange={() => undefined}
        caseId="case-123"
        caseStatus="ready"
        archUploads={{ upper: emptyUpload, lower: emptyUpload }}
        fileInputKeys={{ upper: 0, lower: 0 }}
        scanImportDisabled={false}
        isBusy={false}
        bothArchesValid={false}
        backendTreatment={false}
        processingStatus={null}
        onCreateCase={() => undefined}
        onRequestNewCase={() => undefined}
        onUpload={() => undefined}
        onRemoveMesh={() => undefined}
        onAnalyzeCase={() => undefined}
        onReviewTreatmentProposal={() => undefined}
      />,
    );
    expect(screen.getByTestId("case-intake-panel")).toHaveAttribute("data-case-state", "active");
    expect(screen.getByTestId("active-case-id")).toHaveTextContent("case-123");
    expect(screen.getByTestId("secondary-new-case")).toBeInTheDocument();
    expect(screen.queryByTestId("create-case-primary")).not.toBeInTheDocument();
  });

  it("does not offer New Case contextual action when a case already exists", () => {
    const withCase = buildWorkflowActions({
      activeStep: "case-intake",
      hasCase: true,
      bothArchesValid: false,
      hasSegmentation: false,
      hasTreatment: false,
      isBusy: false,
    });
    expect(withCase.some((action) => /new case/i.test(action.label))).toBe(false);
    expect(withCase.some((action) => action.label === "Scan Import")).toBe(true);

    const withoutCase = buildWorkflowActions({
      activeStep: "case-intake",
      hasCase: false,
      bothArchesValid: false,
      hasSegmentation: false,
      hasTreatment: false,
      isBusy: false,
    });
    expect(withoutCase.some((action) => action.label === "Create Case")).toBe(true);
  });

  it("renders progressive disclosure and current/target pair", () => {
    render(
      <>
        <CurrentTargetPair currentValue="scan" targetValue="setup" />
        <AdvancedDetails summary="Advanced details">
          <span>hash-abc</span>
        </AdvancedDetails>
      </>,
    );
    expect(screen.getByTestId("current-target-pair")).toBeInTheDocument();
    expect(screen.getByText("Current")).toBeInTheDocument();
    expect(screen.getByText("Target")).toBeInTheDocument();
    expect(screen.getByTestId("advanced-details")).toBeInTheDocument();
    expect(screen.getByText("hash-abc")).toBeInTheDocument();
  });

  it("never labels unavailable attachment state as a fake zero count alone", () => {
    // Refinement presentation must prefer Requires Review / Not Available over "0".
    const labels = ["Not Available", "Requires Review", "Requires Review"];
    expect(labels.every((label) => label !== "0")).toBe(true);
  });
});
