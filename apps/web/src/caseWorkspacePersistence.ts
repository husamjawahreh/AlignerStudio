/** Browser workspace continuity for refresh without inventing clinical state. */

export const ACTIVE_CASE_STORAGE_KEY = "alignerstudio.activeCaseId";
export const ACTIVE_WORKSPACE_STORAGE_KEY = "alignerstudio.activeWorkspace";

const WORKSPACE_IDS = new Set([
  "case-intake",
  "analysis",
  "treatment-setup",
  "staging",
  "refinement",
  "validation",
  "production",
]);

export type RememberedWorkspaceId =
  | "case-intake"
  | "analysis"
  | "treatment-setup"
  | "staging"
  | "refinement"
  | "validation"
  | "production";

export function rememberActiveCaseId(caseId: string | null): void {
  try {
    if (!caseId) {
      sessionStorage.removeItem(ACTIVE_CASE_STORAGE_KEY);
      sessionStorage.removeItem(ACTIVE_WORKSPACE_STORAGE_KEY);
      return;
    }
    sessionStorage.setItem(ACTIVE_CASE_STORAGE_KEY, caseId);
  } catch {
    // Private mode / blocked storage — workspace still works for the current tab.
  }
}

export function readRememberedActiveCaseId(): string | null {
  try {
    const value = sessionStorage.getItem(ACTIVE_CASE_STORAGE_KEY);
    return value && value.trim() ? value : null;
  } catch {
    return null;
  }
}

/** Persist workflow step hint only — never clinical geometry or edits. */
export function rememberActiveWorkspace(workspace: RememberedWorkspaceId | null): void {
  try {
    if (!workspace) {
      sessionStorage.removeItem(ACTIVE_WORKSPACE_STORAGE_KEY);
      return;
    }
    if (!WORKSPACE_IDS.has(workspace)) return;
    sessionStorage.setItem(ACTIVE_WORKSPACE_STORAGE_KEY, workspace);
  } catch {
    // ignore
  }
}

export function readRememberedActiveWorkspace(): RememberedWorkspaceId | null {
  try {
    const value = sessionStorage.getItem(ACTIVE_WORKSPACE_STORAGE_KEY);
    if (!value || !WORKSPACE_IDS.has(value)) return null;
    return value as RememberedWorkspaceId;
  } catch {
    return null;
  }
}

/**
 * Choose a recoverable workspace after refresh.
 * Backend treatment presence gates treatment steps; otherwise fall back to intake/analysis.
 */
export function resolveRestoredWorkspace(options: {
  remembered: RememberedWorkspaceId | null;
  hasTreatment: boolean;
  hasProcessingCompleted: boolean;
}): RememberedWorkspaceId {
  const { remembered, hasTreatment, hasProcessingCompleted } = options;
  if (remembered && hasTreatment && remembered !== "case-intake" && remembered !== "analysis") {
    return remembered;
  }
  if (hasTreatment) return "treatment-setup";
  if (hasProcessingCompleted || remembered === "analysis") return "analysis";
  return remembered === "case-intake" || remembered == null ? "case-intake" : "case-intake";
}
