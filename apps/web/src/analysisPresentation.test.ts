import { describe, expect, it } from "vitest";
import type { PipelineDiagnostic } from "./api/client";
import {
  buildAnalysisFindings,
  buildAnalysisOverview,
  formatToothIdentity,
} from "./analysisPresentation";
import type { ReviewToothMesh } from "./review/types";

function tooth(partial: Partial<ReviewToothMesh> & Pick<ReviewToothMesh, "instanceId" | "arch">): ReviewToothMesh {
  return {
    fdiNumber: null,
    confidence: 0.5,
    vertices: [],
    faces: [],
    movement: {
      translationX: 0,
      translationY: 0,
      translationZ: 0,
      rotation: 0,
      tip: 0,
      torque: 0,
      angulation: 0,
      intrusion: 0,
      extrusion: 0,
    },
    validationStatus: "pass",
    validationMessage: "",
    provenance: "experimental",
    fixture: false,
    ...partial,
  };
}

describe("Analysis presentation", () => {
  it("never invents FDI when tooth identity is semantic-only", () => {
    expect(formatToothIdentity({ instanceId: 3, fdiNumber: null, toothRef: "upper:instance:3" })).toBe(
      "upper:instance:3",
    );
    expect(formatToothIdentity({ instanceId: 11, fdiNumber: 11, toothRef: null })).toBe("FDI 11");
  });

  it("does not present a runtime blocker as zero detected teeth", () => {
    const diagnostic: PipelineDiagnostic = {
      state: "model_unavailable",
      source_kind: "uploaded_real_case",
      segmentation_runtime_ms: null,
      total_runtime_ms: 1,
      tooth_instance_count: 0,
      identification_confidence: null,
      identified_teeth: 0,
      uncertain_teeth: 0,
      unidentified_teeth: 0,
      validation_findings: [],
      failures: ["ToothInstanceNet REAL_CASE inference is blocked by environment."],
      arch_analysis_available: false,
      notes: [],
      fixture: false,
      segmentation_truth_state: "blocked_by_environment",
      runtime_blocker: "Missing: torch, pointops, NVIDIA driver",
    };
    const overview = buildAnalysisOverview({ diagnostic, teeth: [] });
    expect(overview.stateLabel).toBe("Blocked by environment");
    expect(overview.countsAvailable).toBe(false);
    expect(overview.segmentationTruthState).toBe("blocked_by_environment");
    expect(buildAnalysisFindings({ diagnostic, validation: null })[0]?.text).toContain(
      "blocked by environment",
    );
  });

  it("reports unavailable anatomy fields when analysis has not run", () => {
    const overview = buildAnalysisOverview({ diagnostic: null, teeth: [] });
    expect(overview.ran).toBe(false);
    expect(overview.stateLabel).toBe("Not run");
    expect(overview.archAnalysisAvailable).toBeNull();
    expect(buildAnalysisFindings({ diagnostic: null, validation: null })[0]?.kind).toBe("gap");
  });

  it("surfaces only reported counts and findings from the diagnostic payload", () => {
    const diagnostic: PipelineDiagnostic = {
      state: "identification_incomplete",
      source_kind: "validated_real_case",
      segmentation_runtime_ms: 10,
      total_runtime_ms: 20,
      tooth_instance_count: 28,
      identification_confidence: null,
      identified_teeth: 0,
      uncertain_teeth: 2,
      unidentified_teeth: 28,
      validation_findings: [],
      failures: [],
      arch_analysis_available: false,
      notes: ["semantic only"],
      fixture: true,
      experimental: true,
      missing_fdi_numbers: [],
      duplicate_fdi_numbers: [],
      excluded_fragment_count: 1,
      anatomical_intelligence: {
        anatomy_extent: "crown_only_stl",
        landmarks_available: false,
        local_axes_available: true,
        movement_frames_available: true,
        arch_orientation_available: false,
        arch_form_available: false,
        midline_available: false,
        occlusion: {
          availability: "unavailable",
          upper_lower_registration: "unavailable",
          occlusal_relationship: "unavailable",
          bite_record: "unavailable",
          occlusal_contacts: "unavailable",
          contact_count: null,
          notes: ["No bite record"],
          provenance: "experimental",
          fixture: true,
        },
        data_quality: {
          scale_validation: "unverified",
          units: "unverified",
          mesh_quality: "unverified",
          incomplete_scans: false,
          missing_teeth: true,
          ambiguous_identity: true,
          incomplete_occlusion: true,
          missing_anatomy: true,
          anatomy_extent: "crown_only_stl",
          findings: ["Missing anatomy: roots not in STL"],
          provenance: "experimental",
          fixture: true,
          requires_review: true,
        },
      },
      tooth_instances: [
        {
          instance_id: 1,
          fdi_number: null,
          tooth_ref: "upper:instance:1",
          arch: "upper",
          vertices: [],
          faces: [],
          centroid: [0, 0, 0],
          confidence: 0,
          landmarks: null,
          coordinate_system: {
            origin: [0, 0, 0],
            lateral_axis: [1, 0, 0],
            anterior_axis: [0, 1, 0],
            vertical_axis: [0, 0, 1],
            semantics: ["engineering-reference-axis", "engineering-reference-axis", "engineering-reference-axis"],
          },
          provenance: "experimental",
          fixture: true,
          experimental: true,
          anatomy_extent: "crown_only_stl",
        },
      ],
    };
    const teeth = [
      tooth({ instanceId: 1, arch: "upper" }),
      tooth({ instanceId: 2, arch: "lower" }),
    ];
    const overview = buildAnalysisOverview({ diagnostic, teeth });
    expect(overview.instanceCount).toBe(28);
    expect(overview.upperCount).toBe(1);
    expect(overview.lowerCount).toBe(1);
    expect(overview.archAnalysisAvailable).toBe(false);
    expect(overview.landmarksAvailable).toBe(false);
    expect(overview.localAxesAvailable).toBe(true);
    expect(overview.occlusionAvailability).toBe("unavailable");
    expect(overview.anatomyExtent).toBe("crown_only_stl");
    expect(overview.scaleValidation).toBe("unverified");
    const findings = buildAnalysisFindings({ diagnostic, validation: null });
    expect(findings.some((finding) => finding.text.includes("Uncertain teeth: 2"))).toBe(true);
    expect(findings.some((finding) => finding.text.includes("Excluded zero-face fragments: 1"))).toBe(
      true,
    );
    expect(findings.some((finding) => finding.text.includes("Missing anatomy"))).toBe(true);
  });

  it("reports arch form metrics only when arch_measurements are present", () => {
    const diagnostic: PipelineDiagnostic = {
      state: "planning_ready",
      source_kind: "uploaded_real_case",
      segmentation_runtime_ms: 1,
      total_runtime_ms: 2,
      tooth_instance_count: 16,
      identification_confidence: 0.9,
      identified_teeth: 16,
      uncertain_teeth: 0,
      unidentified_teeth: 0,
      validation_findings: [],
      failures: [],
      arch_analysis_available: true,
      notes: [],
      arch_measurements: {
        arch: "upper",
        centerline: [],
        ordered_instance_ids: [0, 1],
        total_width: 42.5,
        left_half_width: 21,
        right_half_width: 21.5,
        anterior_width: 10,
        posterior_width: 40,
        consecutive_tooth_distances: [1.2, 1.1],
        anterior_to_posterior_order: [0, 1],
        orientation_lateral_axis: [1, 0, 0],
        orientation_anterior_axis: [0, 1, 0],
        orientation_vertical_axis: [0, 0, 1],
        geometric_midline_point: [0, 0, 0],
        provenance: "fixture",
        fixture: true,
        notes: "descriptive",
      },
      anatomical_intelligence: {
        anatomy_extent: "crown_only_stl",
        landmarks_available: true,
        local_axes_available: true,
        movement_frames_available: true,
        arch_orientation_available: true,
        arch_form_available: true,
        midline_available: true,
        occlusion: {
          availability: "unavailable",
          upper_lower_registration: "unavailable",
          occlusal_relationship: "unavailable",
          bite_record: "unavailable",
          occlusal_contacts: "unavailable",
          contact_count: null,
          notes: [],
          provenance: "fixture",
          fixture: true,
        },
        data_quality: {
          scale_validation: "unverified",
          units: "unverified",
          mesh_quality: "watertight",
          incomplete_scans: false,
          missing_teeth: false,
          ambiguous_identity: false,
          incomplete_occlusion: true,
          missing_anatomy: true,
          anatomy_extent: "crown_only_stl",
          findings: [],
          provenance: "fixture",
          fixture: true,
          requires_review: true,
        },
      },
    };
    const overview = buildAnalysisOverview({ diagnostic, teeth: [] });
    expect(overview.archTotalWidth).toBe(42.5);
    expect(overview.interToothCount).toBe(2);
    expect(overview.midlineAvailable).toBe(true);
    expect(overview.archOrientationAvailable).toBe(true);
  });
});
