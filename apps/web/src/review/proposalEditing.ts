import type { ProposalStatus, ReviewBundle } from "./types";
import { engineeringFixtureBundle } from "./fixtureData";

export function setIPRStatus(
  bundle: ReviewBundle,
  siteId: string,
  status: ProposalStatus,
): ReviewBundle {
  return {
    ...bundle,
    iprSites: bundle.iprSites.map((site) => (site.siteId === siteId ? { ...site, status } : site)),
  };
}

export function modifyIPRAmount(
  bundle: ReviewBundle,
  siteId: string,
  amount: number,
): ReviewBundle {
  if (!Number.isFinite(amount) || amount < 0)
    throw new Error("IPR amount must be a finite non-negative value");
  return {
    ...bundle,
    iprSites: bundle.iprSites.map((site) =>
      site.siteId === siteId
        ? { ...site, proposedAmount: amount, status: "doctor_modified" }
        : site,
    ),
  };
}

export function setAttachmentStatus(
  bundle: ReviewBundle,
  siteId: string,
  status: ProposalStatus,
): ReviewBundle {
  return {
    ...bundle,
    attachmentSites: bundle.attachmentSites.map((site) =>
      site.siteId === siteId ? { ...site, status } : site,
    ),
  };
}

export function resetAdjunctProposals(original: ReviewBundle): ReviewBundle {
  return {
    ...engineeringFixtureBundle,
    stages: original.stages,
    editHistory: [],
  };
}
