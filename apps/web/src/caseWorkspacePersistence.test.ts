import { describe, expect, it, beforeEach } from "vitest";
import {
  ACTIVE_CASE_STORAGE_KEY,
  ACTIVE_WORKSPACE_STORAGE_KEY,
  readRememberedActiveCaseId,
  readRememberedActiveWorkspace,
  rememberActiveCaseId,
  rememberActiveWorkspace,
  resolveRestoredWorkspace,
} from "./caseWorkspacePersistence";

describe("WP-13 browser workspace persistence", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("remembers case id and workspace step together", () => {
    rememberActiveCaseId("case-123");
    rememberActiveWorkspace("staging");
    expect(sessionStorage.getItem(ACTIVE_CASE_STORAGE_KEY)).toBe("case-123");
    expect(sessionStorage.getItem(ACTIVE_WORKSPACE_STORAGE_KEY)).toBe("staging");
    expect(readRememberedActiveCaseId()).toBe("case-123");
    expect(readRememberedActiveWorkspace()).toBe("staging");
  });

  it("clears workspace when case id is cleared", () => {
    rememberActiveCaseId("case-123");
    rememberActiveWorkspace("validation");
    rememberActiveCaseId(null);
    expect(readRememberedActiveCaseId()).toBeNull();
    expect(readRememberedActiveWorkspace()).toBeNull();
  });

  it("rejects unknown workspace ids", () => {
    rememberActiveWorkspace("not-a-step" as never);
    expect(readRememberedActiveWorkspace()).toBeNull();
  });

  it("restores treatment workspace from durable hint when treatment exists", () => {
    expect(
      resolveRestoredWorkspace({
        remembered: "production",
        hasTreatment: true,
        hasProcessingCompleted: true,
      }),
    ).toBe("production");
  });

  it("does not restore treatment steps without treatment", () => {
    expect(
      resolveRestoredWorkspace({
        remembered: "staging",
        hasTreatment: false,
        hasProcessingCompleted: true,
      }),
    ).toBe("analysis");
  });
});
