import type { Case, MeshValidationResult, TreatmentPlan } from "@alignerstudio/contracts";

/** Frontend-only view model combining case + latest validation + plan for one screen. */
export interface CaseWorkspaceViewModel {
  case: Case;
  latestValidation?: MeshValidationResult;
  plan?: TreatmentPlan;
}

export function isFixtureData(entity: { fixture: boolean }): boolean {
  return entity.fixture === true;
}
