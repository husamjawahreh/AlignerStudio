/** Browser workspace continuity for refresh without inventing clinical state. */

export const ACTIVE_CASE_STORAGE_KEY = "alignerstudio.activeCaseId";

export function rememberActiveCaseId(caseId: string | null): void {
  try {
    if (!caseId) {
      sessionStorage.removeItem(ACTIVE_CASE_STORAGE_KEY);
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
