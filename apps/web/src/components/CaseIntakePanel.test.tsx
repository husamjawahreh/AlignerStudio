import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CaseIntakePanel } from "./CaseIntakePanel";

describe("CaseIntakePanel intake quality", () => {
  it("shows format, readiness, and does not claim occlusion or FDI", () => {
    render(
      <CaseIntakePanel
        patientReference="local"
        onPatientReferenceChange={vi.fn()}
        caseId="case-1"
        caseStatus="mesh_uploaded"
        archUploads={{
          upper: {
            filename: "scan.stl",
            size: 2048,
            state: "valid",
            validation: { triangle_count: 12, is_watertight: false, errors: [] },
            intake: {
              format: "stl_binary",
              readiness: "READY_WITH_WARNINGS",
              vertex_count: 8,
              face_count: 12,
              warnings: ["open_surface"],
              arch: { arch: "upper", truth: "USER_PROVIDED" },
              occlusion_established: false,
              fdi_assigned: false,
            },
          },
          lower: { filename: "", size: 0, state: "empty", validation: null, intake: null },
        }}
        fileInputKeys={{ upper: 0, lower: 0 }}
        scanImportDisabled={false}
        isBusy={false}
        bothArchesValid={false}
        backendTreatment={false}
        processingStatus={null}
        onCreateCase={vi.fn()}
        onUpload={vi.fn()}
        onRemoveMesh={vi.fn()}
        onAnalyzeCase={vi.fn()}
        onReviewTreatmentProposal={vi.fn()}
      />,
    );
    expect(screen.getByTestId("upper-intake-quality").textContent).toContain("READY_WITH_WARNINGS");
    expect(screen.getByTestId("upper-intake-quality").textContent).toContain("stl_binary");
    expect(screen.getByText("open_surface")).toBeInTheDocument();
    expect(screen.getByText("Occlusion is not inferred. FDI is not assigned.")).toBeInTheDocument();
    expect(screen.getByLabelText("Upper Arch scan")).toHaveAttribute("accept", ".stl,.ply,.obj");
  });

  it("keeps preparation actions on the form and does not claim clinical axes", () => {
    const onPrepare = vi.fn();
    const onDismissPreview = vi.fn();
    render(
      <CaseIntakePanel
        patientReference="local"
        onPatientReferenceChange={vi.fn()}
        caseId="case-1"
        caseStatus="mesh_uploaded"
        archUploads={{
          upper: {
            filename: "scan.stl",
            size: 2048,
            state: "valid",
            intake: {
              format: "stl_binary",
              readiness: "READY_WITH_WARNINGS",
              vertex_count: 8,
              face_count: 12,
              preparation: {
                readiness: "PREPARED",
                operations: [{ operation: "orient", truth_state: "USER_PROVIDED", clinical_axes: false }],
                quality_comparison: {
                  prepared: { vertex_count: 8, face_count: 12, warnings: ["open_surface"] },
                },
                fdi_assigned: false,
                occlusion_established: false,
                clinical_axes: false,
                clinically_segmented: false,
              },
            },
          },
          lower: { filename: "", size: 0, state: "empty", validation: null, intake: null },
        }}
        fileInputKeys={{ upper: 0, lower: 0 }}
        scanImportDisabled={false}
        isBusy={false}
        bothArchesValid={false}
        backendTreatment={false}
        processingStatus={null}
        onCreateCase={vi.fn()}
        onUpload={vi.fn()}
        onRemoveMesh={vi.fn()}
        onAnalyzeCase={vi.fn()}
        onReviewTreatmentProposal={vi.fn()}
        preparationPreview={{
          arch: "upper",
          body: {
            limitations: "Faces are kept or dropped by centroid.",
            clinical_axes: false,
          },
        }}
        onPrepare={onPrepare}
        onDismissPreview={onDismissPreview}
      />,
    );
    expect(screen.getByTestId("upper-preparation-status").textContent).toContain("PREPARED");
    expect(screen.getByTestId("upper-preparation-status").textContent).toContain(
      "Accept for a later segmentation step",
    );
    expect(screen.getByTestId("upper-preparation-history").textContent).toContain("USER_PROVIDED");
    expect(screen.getAllByText(/FDI is not assigned/).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Rotate 90° Z" }));
    expect(onPrepare).toHaveBeenCalledWith(
      "upper",
      expect.objectContaining({
        action: "apply",
        operation: "orient",
        parameters: expect.objectContaining({ method: "user_transform" }),
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Cancel preview" }));
    expect(onDismissPreview).toHaveBeenCalled();
  });

  it("shows a preparation job and blocks an equivalent submit while it is active", () => {
    const onPrepare = vi.fn();
    const onCancel = vi.fn();
    render(
      <CaseIntakePanel
        patientReference="local"
        onPatientReferenceChange={vi.fn()}
        caseId="case-1"
        caseStatus="mesh_uploaded"
        archUploads={{
          upper: {
            filename: "scan.stl",
            size: 2048,
            state: "valid",
            intake: {
              format: "stl_binary",
              readiness: "READY_WITH_WARNINGS",
              vertex_count: 8,
              face_count: 12,
              preparation: { readiness: "NOT_PREPARED", operations: [] },
            },
          },
          lower: { filename: "", size: 0, state: "empty", validation: null, intake: null },
        }}
        fileInputKeys={{ upper: 0, lower: 0 }}
        scanImportDisabled={false}
        isBusy={false}
        bothArchesValid={false}
        backendTreatment={false}
        processingStatus={null}
        onCreateCase={vi.fn()}
        onUpload={vi.fn()}
        onRemoveMesh={vi.fn()}
        onAnalyzeCase={vi.fn()}
        onReviewTreatmentProposal={vi.fn()}
        onPrepare={onPrepare}
        onDismissPreview={vi.fn()}
        onCancelPreparationJob={onCancel}
        preparationJob={{
          arch: "upper",
          job: {
            job_id: "job-1",
            operation: "orient",
            state: "running",
            progress: 0.5,
            duration_ms: 1200,
            source_artifact_hash: "60aaafed8781",
            output_artifact_hash: null,
            clinical_axes: false,
          },
        }}
      />,
    );
    const status = screen.getByTestId("upper-preparation-job");
    expect(status.textContent).toContain("orient running");
    expect(status.textContent).toContain("50%");
    expect(status.textContent).toContain("1.2s");
    expect(status.textContent).toContain("source 60aaafed8781");
    expect(status.textContent).toContain("derived pending");
    expect(screen.getByRole("button", { name: "Rotate 90° Z" })).toBeDisabled();
    fireEvent.click(screen.getByTestId("upper-preparation-cancel-job"));
    expect(onCancel).toHaveBeenCalled();
    expect(onPrepare).not.toHaveBeenCalled();
  });
});
