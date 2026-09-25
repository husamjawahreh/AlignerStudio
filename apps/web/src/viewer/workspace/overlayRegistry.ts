/**
 * Runtime overlay registry — lifecycle + truth-aware visibility (WP-03).
 * Only overlays with genuine source data may be enabled.
 */

import type { IntelligenceTruthState } from "@alignerstudio/contracts";
import {
  WORKSPACE_OVERLAY_CAPABILITIES,
  type OverlayCapability,
  type OverlayKind,
} from "./overlayArchitecture";

export type OverlaySource =
  | "presentation"
  | "pipeline"
  | "validation"
  | "intelligence"
  | "treatment"
  | "unavailable";

export interface OverlayRegistration {
  id: string;
  kind: OverlayKind | "movement_vectors" | "original_scan" | "target_ghost" | "gingiva" | "tooth_labels";
  label: string;
  source: OverlaySource;
  enabled: boolean;
  visible: boolean;
  truthState: IntelligenceTruthState;
  renderingLayer: string;
  reason: string;
  provenance?: string | null;
}

export interface OverlayRegistry {
  overlays: OverlayRegistration[];
  get(id: string): OverlayRegistration | undefined;
  setVisible(id: string, visible: boolean): OverlayRegistry;
  setEnabled(id: string, enabled: boolean): OverlayRegistry;
  listVisible(): OverlayRegistration[];
}

const BASE_PRESENTATION: OverlayRegistration[] = [
  {
    id: "original_scan",
    kind: "original_scan",
    label: "Original scan",
    source: "presentation",
    enabled: true,
    visible: false,
    truthState: "computed",
    renderingLayer: "ReferenceLayer",
    reason: "Uploaded scan meshes when present.",
  },
  {
    id: "gingiva",
    kind: "gingiva",
    label: "Gingiva",
    source: "presentation",
    enabled: true,
    visible: true,
    truthState: "not_available",
    renderingLayer: "UpperGingiva|LowerGingiva",
    reason: "Synthetic gingiva is presentation-only unless real gingiva is supplied.",
    provenance: "presentation_only",
  },
  {
    id: "target_ghost",
    kind: "target_ghost",
    label: "Target ghost",
    source: "treatment",
    enabled: true,
    visible: true,
    truthState: "requires_review",
    renderingLayer: "TreatmentLayer",
    reason: "Proposed setup ghost when a treatment stage exists.",
  },
  {
    id: "movement_vectors",
    kind: "movement_vectors",
    label: "Movement vectors",
    source: "treatment",
    enabled: true,
    visible: true,
    truthState: "computed",
    renderingLayer: "TreatmentLayer",
    reason: "Remaining-movement vectors between current and target stages.",
  },
  {
    id: "tooth_labels",
    kind: "tooth_labels",
    label: "Tooth labels",
    source: "presentation",
    enabled: true,
    visible: true,
    truthState: "computed",
    renderingLayer: "AnnotationLayer",
    reason: "Labels show tooth_ref or FDI only when genuinely present.",
  },
  {
    id: "gizmo",
    kind: "gizmo",
    label: "Movement gizmo",
    source: "treatment",
    enabled: true,
    visible: true,
    truthState: "requires_review",
    renderingLayer: "InteractionLayer",
    reason: "Translate/rotate gizmo when a tooth is selected.",
  },
  {
    id: "validation",
    kind: "validation",
    label: "Validation overlays",
    source: "validation",
    enabled: false,
    visible: false,
    truthState: "not_available",
    renderingLayer: "ValidationLayer",
    reason: "3D validation overlays require per-finding spatial binding; findings remain in panels.",
  },
  {
    id: "measurement",
    kind: "measurement",
    label: "Measurements",
    source: "intelligence",
    enabled: false,
    visible: false,
    truthState: "not_available",
    renderingLayer: "MeasurementLayer",
    reason: "Measurement overlays are reserved; WP-02 metrics are inspectable in panels.",
  },
  {
    id: "local_frames",
    kind: "local_frames",
    label: "Local frames",
    source: "unavailable",
    enabled: false,
    visible: false,
    truthState: "not_available",
    renderingLayer: "MeasurementLayer",
    reason: "Clinical dental axes are not available; mesh PCA is not shown as clinical axes.",
  },
  {
    id: "occlusion",
    kind: "section",
    label: "Occlusion",
    source: "unavailable",
    enabled: false,
    visible: false,
    truthState: "not_available",
    renderingLayer: "OcclusionLayer",
    reason: "Occlusion remains not available without bite/registration evidence.",
  },
];

function cloneRegistry(overlays: OverlayRegistration[]): OverlayRegistry {
  const list = overlays.map((item) => ({ ...item }));
  return {
    overlays: list,
    get(id) {
      return list.find((item) => item.id === id);
    },
    setVisible(id, visible) {
      return cloneRegistry(
        list.map((item) => (item.id === id && item.enabled ? { ...item, visible } : item)),
      );
    },
    setEnabled(id, enabled) {
      return cloneRegistry(
        list.map((item) =>
          item.id === id ? { ...item, enabled, visible: enabled ? item.visible : false } : item,
        ),
      );
    },
    listVisible() {
      return list.filter((item) => item.enabled && item.visible);
    },
  };
}

export function createOverlayRegistry(
  overrides: Partial<Record<string, Partial<OverlayRegistration>>> = {},
): OverlayRegistry {
  const overlays = BASE_PRESENTATION.map((item) => ({
    ...item,
    ...(overrides[item.id] ?? {}),
  }));
  return cloneRegistry(overlays);
}

/** Map static capability table into registry for UI honesty checks. */
export function capabilityOverlays(): OverlayCapability[] {
  return [...WORKSPACE_OVERLAY_CAPABILITIES];
}

/** Synthetic gingiva must never enter clinical calculation paths. */
export function isClinicalGeometryOverlay(overlay: OverlayRegistration): boolean {
  if (overlay.id === "gingiva" && overlay.provenance === "presentation_only") return false;
  if (overlay.source === "presentation" || overlay.source === "unavailable") return false;
  return overlay.truthState === "verified" || overlay.truthState === "computed";
}
