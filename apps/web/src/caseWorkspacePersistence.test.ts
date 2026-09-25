import { describe, expect, it, beforeEach } from "vitest";
import {
  ACTIVE_CASE_STORAGE_KEY,
  readRememberedActiveCaseId,
  rememberActiveCaseId,
} from "./caseWorkspacePersistence";

describe("caseWorkspacePersistence", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("remembers and reads the active case id", () => {
    rememberActiveCaseId("case-123");
    expect(sessionStorage.getItem(ACTIVE_CASE_STORAGE_KEY)).toBe("case-123");
    expect(readRememberedActiveCaseId()).toBe("case-123");
  });

  it("clears the remembered case id", () => {
    rememberActiveCaseId("case-123");
    rememberActiveCaseId(null);
    expect(readRememberedActiveCaseId()).toBeNull();
  });
});
