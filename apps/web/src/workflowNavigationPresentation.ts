import type { ReviewBundle, ReviewStage } from "./review/types";

export interface WorkflowNavRow {
  id: string;
  label: string;
  value: string;
}

/** Refinement navigation — existing edit/proposal counts only (no P4 tooling). */
export function buildRefinementNavigation(bundle: ReviewBundle): WorkflowNavRow[] {
  return [
    {
      id: "tooth-controls",
      label: "Tooth Controls",
      value: bundle.realDataAvailable && bundle.stages.length > 0 ? "Ready" : "Unavailable",
    },
    {
      id: "movement",
      label: "Movement",
      value: bundle.realDataAvailable && bundle.stages.length > 0 ? "Ready" : "Unavailable",
    },
    {
      id: "attachments",
      label: "Attachments",
      value: String(bundle.attachmentSites.length),
    },
    {
      id: "ipr",
      label: "IPR",
      value: String(bundle.iprSites.length),
    },
    {
      id: "edit-history",
      label: "Edit History",
      value: String(bundle.editHistory.length),
    },
  ];
}

const VALIDATION_NAV: readonly {
  id: keyof NonNullable<ReviewBundle["validationSummary"]> | "reviewStatus";
  label: string;
  summaryKey?: keyof NonNullable<ReviewBundle["validationSummary"]>;
}[] = [
  { id: "geometry", label: "Geometry", summaryKey: "geometry" },
  { id: "contacts", label: "Contacts", summaryKey: "contacts" },
  { id: "proximity", label: "Proximity", summaryKey: "proximity" },
  { id: "collisions", label: "Collisions", summaryKey: "collisions" },
  { id: "movementConstraints", label: "Movement Constraints", summaryKey: "movementConstraints" },
  { id: "stageConsistency", label: "Stage Consistency", summaryKey: "stageConsistency" },
  { id: "dataCompleteness", label: "Data Completeness", summaryKey: "dataCompleteness" },
  { id: "reviewStatus", label: "Review Status", summaryKey: "doctorReview" },
];

/** Validation navigation — maps existing validationSummary / stage counts only. */
export function buildValidationNavigation(
  bundle: ReviewBundle,
  stage: ReviewStage | null | undefined,
): WorkflowNavRow[] {
  const summary = bundle.validationSummary;
  return VALIDATION_NAV.map((item) => {
    if (summary && item.summaryKey) {
      return {
        id: item.id,
        label: item.label,
        value: String(summary[item.summaryKey]).replaceAll("_", " "),
      };
    }
    if (stage) {
      if (item.id === "collisions") {
        return { id: item.id, label: item.label, value: String(stage.collisionCount) };
      }
      if (item.id === "proximity") {
        return { id: item.id, label: item.label, value: String(stage.proximityCount) };
      }
      if (item.id === "contacts") {
        return { id: item.id, label: item.label, value: String(stage.contactCount) };
      }
      if (item.id === "geometry") {
        return {
          id: item.id,
          label: item.label,
          value: stage.validationStatus.replaceAll("_", " "),
        };
      }
      if (item.id === "reviewStatus") {
        return { id: item.id, label: item.label, value: "required" };
      }
    }
    return { id: item.id, label: item.label, value: "Unavailable" };
  });
}

/** Production navigation — existing package fields only (no manufacturing engine). */
export function buildProductionNavigation(bundle: ReviewBundle): WorkflowNavRow[] {
  const finalStage = bundle.stages.at(-1);
  const packageReady = bundle.realDataAvailable && bundle.stages.length > 0;
  return [
    {
      id: "appliance-stages",
      label: "Appliance Stages",
      value: bundle.stages.length > 0 ? String(bundle.stages.length) : "Unavailable",
    },
    {
      id: "manufacturing-preparation",
      label: "Manufacturing Preparation",
      value: packageReady ? "Uses Export Package" : "Unavailable",
    },
    {
      id: "ipr-report",
      label: "IPR Report",
      value: String(bundle.iprSites.length),
    },
    {
      id: "attachment-plan",
      label: "Attachment Plan",
      value: String(bundle.attachmentSites.length),
    },
    {
      id: "auxiliary-features",
      label: "Auxiliary Features",
      value: "Unavailable",
    },
    {
      id: "export-package",
      label: "Export Package",
      value: packageReady ? "Ready" : "Incomplete",
    },
    {
      id: "production-qa",
      label: "Production QA",
      value: finalStage?.validationStatus.replaceAll("_", " ") ?? "Unavailable",
    },
  ];
}
