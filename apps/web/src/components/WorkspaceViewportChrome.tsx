/**
 * Compact CAD viewport chrome: arch isolation + truth-aware status.
 * Does not invent clinical capabilities.
 */

import type { CaseDentalIntelligencePayload } from "@alignerstudio/contracts";
import { formatTruthState } from "../analysisPresentation";
import {
  createOverlayRegistry,
  type OverlayRegistry,
} from "../viewer/workspace";

export type ArchIsolationMode = "both" | "upper" | "lower";

interface WorkspaceViewportChromeProps {
  archMode: ArchIsolationMode;
  onArchMode: (mode: ArchIsolationMode) => void;
  isolateSelected: boolean;
  onIsolateSelected: (value: boolean) => void;
  selectedToothKey: string | null;
  dentalIntelligence?: CaseDentalIntelligencePayload | null;
  overlayRegistry?: OverlayRegistry;
  onOverlayVisibility?: (id: string, visible: boolean) => void;
}

export function WorkspaceViewportChrome({
  archMode,
  onArchMode,
  isolateSelected,
  onIsolateSelected,
  selectedToothKey,
  dentalIntelligence = null,
  overlayRegistry,
  onOverlayVisibility,
}: WorkspaceViewportChromeProps): JSX.Element {
  const registry = overlayRegistry ?? createOverlayRegistry();
  const readiness = dentalIntelligence?.capability_readiness;

  return (
    <div className="workspace-viewport-chrome" data-testid="workspace-viewport-chrome">
      <div className="chrome-group" aria-label="Arch isolation">
        <span className="eyebrow">Arch</span>
        {(
          [
            ["both", "Both"],
            ["upper", "Upper"],
            ["lower", "Lower"],
          ] as const
        ).map(([mode, label]) => (
          <button
            key={mode}
            type="button"
            className={`viewer-tool ${archMode === mode ? "is-active" : ""}`}
            data-testid={`arch-mode-${mode}`}
            onClick={() => onArchMode(mode)}
          >
            {label}
          </button>
        ))}
        <button
          type="button"
          className={`viewer-tool ${isolateSelected ? "is-active" : ""}`}
          data-testid="isolate-selected-tooth"
          disabled={!selectedToothKey}
          onClick={() => onIsolateSelected(!isolateSelected)}
          title="Isolate selected tooth"
        >
          Isolate tooth
        </button>
      </div>

      <div className="chrome-group" aria-label="Presentation overlays">
        <span className="eyebrow">Overlays</span>
        {registry.overlays
          .filter((item) => item.enabled && ["original_scan", "gingiva", "target_ghost", "movement_vectors", "tooth_labels"].includes(item.id))
          .map((item) => (
            <label className="toggle-row chrome-overlay-toggle" key={item.id}>
              <input
                type="checkbox"
                checked={item.visible}
                disabled={!onOverlayVisibility}
                onChange={(event) => onOverlayVisibility?.(item.id, event.target.checked)}
              />
              <span>
                {item.label}
                <small> · {formatTruthState(item.truthState)}</small>
              </span>
            </label>
          ))}
      </div>

      {readiness && (
        <div className="chrome-group chrome-readiness" aria-label="Intelligence readiness">
          <span className="eyebrow">Readiness</span>
          <div className="cad-stat-row">
            <span>Identity</span>
            <strong>{formatTruthState(readiness.identity_readiness)}</strong>
          </div>
          <div className="cad-stat-row">
            <span>Geometry</span>
            <strong>{formatTruthState(readiness.geometry_readiness)}</strong>
          </div>
          <div className="cad-stat-row">
            <span>Occlusion</span>
            <strong>{formatTruthState(readiness.occlusion_readiness)}</strong>
          </div>
          <div className="cad-stat-row">
            <span>Treatment setup</span>
            <strong>{formatTruthState(readiness.treatment_setup_readiness)}</strong>
          </div>
        </div>
      )}
    </div>
  );
}
