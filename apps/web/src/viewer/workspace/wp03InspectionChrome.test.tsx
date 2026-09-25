import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import type { CaseDentalIntelligencePayload } from "@alignerstudio/contracts";
import { InspectionPanel } from "../../components/InspectionPanel";
import { WorkspaceViewportChrome } from "../../components/WorkspaceViewportChrome";
import { engineeringFixtureBundle } from "../../review/fixtureData";

const intelligence: CaseDentalIntelligencePayload = {
  contract_version: "dental_intelligence_2.0",
  case_id: "c1",
  job_id: "j1",
  input_hash: "a".repeat(64),
  processing_mode: "real_case",
  generated_at: "2026-09-25T00:00:00+00:00",
  teeth: [
    {
      instance_id: engineeringFixtureBundle.stages[0].teeth[0].instanceId,
      tooth_ref: engineeringFixtureBundle.stages[0].teeth[0].toothRef ?? null,
      arch: engineeringFixtureBundle.stages[0].teeth[0].arch,
      fdi_number: {
        state: "not_available",
        value: null,
        reason: "No FDI",
        algorithm: null,
        algorithm_version: null,
      },
      semantic_label: {
        state: "requires_review",
        value: 1,
        reason: "semantic",
        algorithm: null,
        algorithm_version: null,
      },
      identification_status: "uncertain",
      identification_confidence: null,
      geometry: {
        state: "computed",
        value: {},
        reason: "mesh",
        algorithm: "mesh_geometry_metrics",
        algorithm_version: "mesh_metrics_v1",
      },
      crown_geometry: {
        state: "computed",
        value: true,
        reason: "crown",
        algorithm: "anatomy_extent_stl",
        algorithm_version: "v1",
      },
      root_geometry: {
        state: "not_available",
        value: null,
        reason: "no roots",
        algorithm: null,
        algorithm_version: null,
      },
      landmarks: {
        state: "not_available",
        value: null,
        reason: "none",
        algorithm: null,
        algorithm_version: null,
      },
      local_coordinate_frame: {
        state: "not_available",
        value: null,
        reason: "none",
        algorithm: null,
        algorithm_version: null,
      },
      clinical_dental_axes: {
        state: "not_available",
        value: null,
        reason: "none",
        algorithm: null,
        algorithm_version: null,
      },
      mesh_principal_directions: {
        state: "computed",
        value: [],
        reason: "pca",
        algorithm: "mesh_geometry_metrics",
        algorithm_version: "mesh_metrics_v1",
      },
      quality_findings: [],
      overall_truth_state: "requires_review",
      provenance: "experimental",
      fixture: false,
      source_mesh_sha256: "b".repeat(64),
    },
  ],
  arches: [],
  occlusion: {
    state: "not_available",
    value: null,
    reason: "no bite",
    algorithm: "occlusion_gate",
    algorithm_version: null,
  },
  data_quality_findings: [],
  capability_readiness: {
    identity_readiness: "requires_review",
    geometry_readiness: "computed",
    axis_readiness: "not_available",
    occlusion_readiness: "not_available",
    treatment_setup_readiness: "requires_review",
    validation_readiness: "requires_review",
    reasons: [],
  },
  overall_truth_state: "requires_review",
  provenance: "experimental",
  fixture: false,
};

describe("WP-03 inspection + chrome", () => {
  it("shows tooth_ref and unavailable FDI/axes honestly", () => {
    const base = engineeringFixtureBundle.stages[0].teeth[0];
    const tooth = {
      ...base,
      fdiNumber: null as number | null,
      toothRef: base.toothRef ?? `${base.arch}:instance:${base.instanceId}`,
      confidence: 0,
    };
    const aligned: CaseDentalIntelligencePayload = {
      ...intelligence,
      teeth: [
        {
          ...intelligence.teeth[0],
          instance_id: tooth.instanceId,
          tooth_ref: tooth.toothRef,
          arch: tooth.arch,
        },
      ],
    };
    render(<InspectionPanel tooth={tooth} dentalIntelligence={aligned} />);
    expect(screen.getByTestId("inspection-tooth-ref").textContent).toMatch(
      new RegExp(tooth.toothRef!.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")),
    );
    expect(screen.getByTestId("inspection-fdi-truth").textContent).toMatch(/Not Available/i);
    expect(screen.getByTestId("inspection-intelligence").textContent).toMatch(/Clinical dental axes/);
    expect(screen.getByTestId("inspection-intelligence").textContent).toMatch(/Not Available/);
  });

  it("exposes arch isolation controls without inventing clinical overlays", () => {
    render(
      <WorkspaceViewportChrome
        archMode="both"
        onArchMode={() => undefined}
        isolateSelected={false}
        onIsolateSelected={() => undefined}
        selectedToothKey="upper:instance:0"
        dentalIntelligence={intelligence}
      />,
    );
    expect(screen.getByTestId("arch-mode-upper")).toBeTruthy();
    expect(screen.getByTestId("isolate-selected-tooth")).toBeTruthy();
    expect(screen.getAllByText(/Not Available/).length).toBeGreaterThan(0);
  });
});
