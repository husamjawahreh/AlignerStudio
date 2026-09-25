import type { ReviewBundle, ReviewStage } from "./review/types";

export interface WorkflowNavRow {
  id: string;
  label: string;
  value: string;
}

function clinicalNavLabel(
  sitesLength: number,
  readiness: string | undefined,
  freshness: string | undefined,
  emptyLabel: string,
): string {
  if (freshness === "stale") return "Stale — regenerate";
  if (readiness === "not_available" || readiness === "unavailable") {
    return emptyLabel;
  }
  if (sitesLength === 0) return emptyLabel;
  if (readiness === "requires_review") {
    return `${sitesLength} · requires review`;
  }
  return String(sitesLength);
}

/** Refinement navigation — honest clinical-tool state (never fake clinical zeros). */
export function buildRefinementNavigation(bundle: ReviewBundle): WorkflowNavRow[] {
  const tools = bundle.clinicalTools;
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
      value: clinicalNavLabel(
        bundle.attachmentSites.length,
        tools?.readiness.attachment_placement,
        tools?.freshness,
        tools ? "Not available" : "Requires review",
      ),
    },
    {
      id: "ipr",
      label: "IPR",
      value: clinicalNavLabel(
        bundle.iprSites.length,
        tools?.readiness.ipr_measurement,
        tools?.freshness,
        tools ? "Not available" : "Requires review",
      ),
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
  { id: "provenance", label: "Provenance", summaryKey: "provenance" },
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

/** Production navigation — honest manufacturing boundary + existing package fields. */
export function buildProductionNavigation(bundle: ReviewBundle): WorkflowNavRow[] {
  const boundary = bundle.manufacturingBoundary;
  const finalStage = bundle.stages.at(-1);
  const packageReady = bundle.realDataAvailable && bundle.stages.length > 0;
  const tools = bundle.clinicalTools;

  const capability = (status: string | undefined, fallback: string): string => {
    if (!status) return fallback;
    return status.replaceAll("_", " ");
  };

  return [
    {
      id: "appliance-stages",
      label: "Appliance Stages",
      value: bundle.stages.length > 0 ? String(bundle.stages.length) : "Unavailable",
    },
    {
      id: "manufacturing-preparation",
      label: "Manufacturing Preparation",
      value: capability(
        boundary?.printableModelPreparation ?? boundary?.applianceShellGeneration,
        packageReady ? "Uses Export Package" : "Unavailable",
      ),
    },
    {
      id: "ipr-report",
      label: "IPR Report",
      value: clinicalNavLabel(
        bundle.iprSites.length,
        tools?.readiness.ipr_measurement,
        tools?.freshness,
        tools ? "Not available" : "Requires review",
      ),
    },
    {
      id: "attachment-plan",
      label: "Attachment Plan",
      value: clinicalNavLabel(
        bundle.attachmentSites.length,
        tools?.readiness.attachment_placement,
        tools?.freshness,
        tools ? "Not available" : "Requires review",
      ),
    },
    {
      id: "auxiliary-features",
      label: "Auxiliary Features",
      value: capability(boundary?.trimlineCutline, "Unavailable"),
    },
    {
      id: "export-package",
      label: "Export Package",
      value: packageReady
        ? capability(boundary?.stageModelExport, "Ready")
        : "Incomplete",
    },
    {
      id: "production-qa",
      label: "Production QA",
      value: capability(
        boundary?.manufacturingQcReport,
        finalStage?.validationStatus.replaceAll("_", " ") ?? "Unavailable",
      ),
    },
  ];
}
