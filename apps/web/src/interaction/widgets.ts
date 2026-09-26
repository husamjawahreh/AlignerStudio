/**
 * Wave 6 contextual widgets.
 * A widget renders only when it adds a fact the status line, inspector, or toolbar does not already own.
 */

export type WidgetId =
  | "selection"
  | "processing"
  | "provenance"
  | "current-target"
  | "staging"
  | "validation"
  | "case-dependency";

export interface WidgetModel {
  id: WidgetId;
  testId: string;
  eyebrow: string;
  value: string;
  detail: string | null;
}

export interface WidgetInput {
  selectionCount: number;
  selectionLabel: string | null;
  selectionArch: string | null;
  groupArches: string | null;
  groupIdentity: "same" | "mixed" | null;
  identityUnresolved: boolean;
  fixture: boolean;
  provenanceLabel: string | null;
  provenanceStripVisible: boolean;
  processing: boolean;
  processingOwnedByStatus: boolean;
  phase: string | null;
  elapsedLabel: string | null;
  serverProgress: number | null;
  canCancel: boolean;
  targetGeometryExists: boolean;
  showTarget: boolean;
  showCurrent: boolean;
  stagingCount: number;
  stagingIndex: number | null;
  stagingStale: boolean;
  stagingTimelineVisible: boolean;
  validationAvailable: boolean;
  validationFindingCount: number | null;
  validationPanelVisible: boolean;
  dependencyText: string | null;
  orientationVisible: boolean;
}

function widget(partial: WidgetModel): WidgetModel {
  return partial;
}

export function resolveWidgets(input: WidgetInput): WidgetModel[] {
  const models: WidgetModel[] = [];

  if (input.selectionCount > 0) {
    const identity = input.fixture
      ? "Fixture / test-only"
      : input.identityUnresolved
        ? "Unresolved"
        : "Authoritative FDI";
    const arch =
      input.selectionCount > 1
        ? input.groupArches || "Arches not set"
        : input.selectionArch || "Arch not set";
    const consistency =
      input.selectionCount > 1
        ? input.groupIdentity === "mixed"
          ? "Identity differs"
          : "Identity agrees"
        : null;
    models.push(
      widget({
        id: "selection",
        testId: "selection-widget",
        eyebrow: input.selectionCount === 1 ? "Selected tooth" : "Selection",
        value: input.selectionCount === 1 ? input.selectionLabel || "tooth_ref" : `${input.selectionCount} teeth`,
        detail: [arch, identity, consistency].filter(Boolean).join(" · "),
      }),
    );
  }

  if (input.processing && !input.processingOwnedByStatus) {
    const progress =
      input.serverProgress == null ? "Progress indeterminate" : `Server progress ${Math.round(input.serverProgress)}%`;
    models.push(
      widget({
        id: "processing",
        testId: "processing-widget",
        eyebrow: "Processing",
        value: input.phase || "Working",
        detail: [input.elapsedLabel, progress, input.canCancel ? "Cancel is available" : null].filter(Boolean).join(" · "),
      }),
    );
  }

  if (input.targetGeometryExists) {
    const mode = input.showCurrent && input.showTarget ? "Current and target" : input.showTarget ? "Target" : "Current";
    models.push(
      widget({
        id: "current-target",
        testId: "current-target-widget",
        eyebrow: "Geometry",
        value: mode,
        detail: "Stored geometry. Not an approval.",
      }),
    );
  }

  if (input.stagingCount > 0 && !input.stagingTimelineVisible) {
    const index = input.stagingIndex == null ? "—" : String(input.stagingIndex + 1);
    models.push(
      widget({
        id: "staging",
        testId: "staging-widget",
        eyebrow: "Stage",
        value: `${index} / ${input.stagingCount}`,
        detail: input.stagingStale ? "Stale relative to the current setup" : "Stored staging. Not a clinical-quality claim.",
      }),
    );
  }

  if (input.validationAvailable && input.validationFindingCount != null && !input.validationPanelVisible) {
    models.push(
      widget({
        id: "validation",
        testId: "validation-widget",
        eyebrow: "Findings",
        value: `${input.validationFindingCount} findings`,
        detail: "Requires review. Not a score and not an approval.",
      }),
    );
  }

  const provenanceLabel = input.provenanceLabel;
  const provenanceIsSpecific =
    provenanceLabel != null && provenanceLabel !== "Not run" && provenanceLabel !== "Not available";
  if (provenanceIsSpecific && provenanceLabel && !input.provenanceStripVisible && !input.fixture) {
    models.push(
      widget({
        id: "provenance",
        testId: "provenance-widget",
        eyebrow: "Provenance",
        value: provenanceLabel,
        detail: "Hashes stay in Advanced details.",
      }),
    );
  }

  if (input.fixture && !input.provenanceStripVisible) {
    models.push(
      widget({
        id: "provenance",
        testId: "provenance-widget",
        eyebrow: "Provenance",
        value: "Fixture / test-only",
        detail: "Not patient inference.",
      }),
    );
  }

  if (input.dependencyText && !input.orientationVisible) {
    models.push(
      widget({
        id: "case-dependency",
        testId: "case-dependency-widget",
        eyebrow: "Dependency",
        value: input.dependencyText,
        detail: null,
      }),
    );
  }

  const rank: Record<WidgetId, number> = {
    selection: 1,
    "current-target": 2,
    validation: 3,
    provenance: 4,
    staging: 5,
    processing: 6,
    "case-dependency": 7,
  };
  return models.sort((a, b) => rank[a.id] - rank[b.id]).slice(0, 2);
}

/** Two widgets may not carry the same sentence. */
export function widgetsDuplicate(models: readonly WidgetModel[]): boolean {
  const texts = models.map((model) => `${model.value} ${model.detail ?? ""}`.trim());
  return new Set(texts).size !== texts.length;
}
