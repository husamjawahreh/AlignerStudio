import { describe, expect, it } from "vitest";
import type { CaseDentalIntelligencePayload } from "@alignerstudio/contracts";
import {
  buildAnalysisFindings,
  buildAnalysisOverview,
  formatTruthState,
} from "./analysisPresentation";

const sampleIntelligence: CaseDentalIntelligencePayload = {
  contract_version: "dental_intelligence_2.0",
  case_id: "c1",
  job_id: "j1",
  input_hash: "a".repeat(64),
  processing_mode: "real_case",
  generated_at: "2026-09-25T00:00:00+00:00",
  teeth: [
    {
      instance_id: 0,
      tooth_ref: "upper:instance:0",
      arch: "upper",
      fdi_number: {
        state: "not_available",
        value: null,
        reason: "Clinical tooth numbering has not been resolved for this tooth.",
        algorithm: null,
        algorithm_version: null,
      },
      semantic_label: {
        state: "requires_review",
        value: 1,
        reason: "Seven-class / semantic label is experimental and not clinical FDI.",
        algorithm: "upstream_semantic_label",
        algorithm_version: null,
      },
      identification_status: "uncertain",
      identification_confidence: null,
      geometry: {
        state: "computed",
        value: { vertex_count: 10 },
        reason: "Deterministic mesh metrics",
        algorithm: "mesh_geometry_metrics",
        algorithm_version: "mesh_metrics_v1",
      },
      crown_geometry: {
        state: "computed",
        value: true,
        reason: "Crown mesh present",
        algorithm: "anatomy_extent_stl",
        algorithm_version: "v1",
      },
      root_geometry: {
        state: "not_available",
        value: null,
        reason: "Root/bone geometry requires CBCT",
        algorithm: null,
        algorithm_version: null,
      },
      landmarks: {
        state: "not_available",
        value: null,
        reason: "No landmark coordinates were supplied",
        algorithm: null,
        algorithm_version: null,
      },
      local_coordinate_frame: {
        state: "not_available",
        value: null,
        reason: "No local coordinate frame was supplied.",
        algorithm: null,
        algorithm_version: null,
      },
      clinical_dental_axes: {
        state: "not_available",
        value: null,
        reason: "Clinical dental axes are not available",
        algorithm: null,
        algorithm_version: null,
      },
      mesh_principal_directions: {
        state: "computed",
        value: [
          [1, 0, 0],
          [0, 1, 0],
          [0, 0, 1],
        ],
        reason: "Mesh PCA principal directions — not clinical dental axes.",
        algorithm: "mesh_geometry_metrics",
        algorithm_version: "mesh_metrics_v1",
      },
      quality_findings: [],
      overall_truth_state: "requires_review",
      provenance: "experimental",
      fixture: false,
    },
  ],
  arches: [
    {
      arch: "upper",
      tooth_instance_count: 1,
      resolved_fdi_count: 0,
      unresolved_identity_count: 1,
      geometry_ready_count: 1,
      landmarks_available_count: 0,
      clinical_axes_available_count: 0,
      quality_findings: [],
      overall_truth_state: "requires_review",
      provenance: "experimental",
      fixture: false,
    },
  ],
  occlusion: {
    state: "not_available",
    value: { availability: "unavailable" },
    reason: "Occlusion unavailable",
    algorithm: "occlusion_gate",
    algorithm_version: null,
  },
  data_quality_findings: ["Missing lower arch segmentation payload."],
  capability_readiness: {
    identity_readiness: "requires_review",
    geometry_readiness: "computed",
    axis_readiness: "not_available",
    occlusion_readiness: "not_available",
    treatment_setup_readiness: "requires_review",
    validation_readiness: "requires_review",
    reasons: ["Treatment setup is not auto-unlocked."],
  },
  overall_truth_state: "requires_review",
  provenance: "experimental",
  fixture: false,
  limitations: ["Clinical FDI is never invented; unresolved identity remains Not Available."],
  counts: {
    tooth_instances: 1,
    resolved_fdi: 0,
    unresolved_identity: 1,
    arch_assigned: 1,
    clinical_axes_available: 0,
    landmarks_available: 0,
    occlusion_available: false,
  },
};

describe("WP-02 Analysis dental intelligence presentation", () => {
  it("renders explicit truth states without inventing clinical facts", () => {
    const overview = buildAnalysisOverview({
      diagnostic: null,
      teeth: [],
      dentalIntelligence: sampleIntelligence,
    });
    expect(overview.ran).toBe(true);
    expect(overview.overallTruthState).toBe("requires_review");
    expect(overview.landmarksTruth).toBe("not_available");
    expect(overview.clinicalAxesTruth).toBe("not_available");
    expect(overview.rootsTruth).toBe("not_available");
    expect(overview.occlusionTruth).toBe("not_available");
    expect(overview.treatmentSetupReadiness).toBe("requires_review");
    expect(overview.landmarksAvailable).toBe(false);
    expect(overview.localAxesAvailable).toBe(false);
    expect(formatTruthState(overview.occlusionTruth)).toBe("Not Available");
  });

  it("does not unlock treatment merely because intelligence exists", () => {
    const findings = buildAnalysisFindings({
      diagnostic: null,
      validation: null,
      dentalIntelligence: sampleIntelligence,
    });
    expect(
      findings.some((item) => item.text.includes("not unlocked by intelligence objects alone")),
    ).toBe(true);
    expect(sampleIntelligence.capability_readiness.treatment_setup_readiness).not.toBe("verified");
  });
});
