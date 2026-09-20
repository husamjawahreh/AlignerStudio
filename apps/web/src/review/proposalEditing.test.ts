import { describe, expect, it } from "vitest";
import { engineeringFixtureBundle } from "./fixtureData";
import {
  modifyIPRAmount,
  resetAdjunctProposals,
  setAttachmentStatus,
  setIPRStatus,
} from "./proposalEditing";

describe("adjunct proposal editing", () => {
  it("modifies and changes proposal lifecycle status immutably", () => {
    const modified = modifyIPRAmount(engineeringFixtureBundle, "fixture-ipr-11-12", 0.2);
    expect(modified.iprSites[0].proposedAmount).toBe(0.2);
    expect(modified.iprSites[0].status).toBe("doctor_modified");
    expect(engineeringFixtureBundle.iprSites[0].proposedAmount).toBe(0.11);
    expect(setIPRStatus(modified, "fixture-ipr-11-12", "accepted").iprSites[0].status).toBe(
      "accepted",
    );
    expect(
      setAttachmentStatus(modified, "fixture-attachment-13", "rejected").attachmentSites[0].status,
    ).toBe("rejected");
  });

  it("resets to the generated fixture proposal", () => {
    const modified = modifyIPRAmount(engineeringFixtureBundle, "fixture-ipr-11-12", 0.2);
    expect(resetAdjunctProposals(modified).iprSites[0].proposedAmount).toBe(0.11);
  });
});
