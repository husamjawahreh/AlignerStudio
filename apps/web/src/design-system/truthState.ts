/**
 * First Version product truth states.
 *
 * Doctor-facing UI must never invent clinical certainty. Every capability
 * surface uses one of these four explicit states.
 */

export type ProductTruthState =
  | "verified"
  | "computed"
  | "requires_review"
  | "not_available";

export const PRODUCT_TRUTH_LABELS: Readonly<Record<ProductTruthState, string>> = {
  verified: "Verified",
  computed: "Computed",
  requires_review: "Requires Review",
  not_available: "Not Available",
};

export interface ProductTruthPresentation {
  state: ProductTruthState;
  label: string;
  /** Doctor-language reason — never engineering jargon. */
  reason?: string;
}

/** Map internal provenance/fixture flags to doctor-facing truth — never invent Verified. */
export function truthFromProvenance(input: {
  fixture?: boolean;
  experimental?: boolean;
  provenance?: string | null;
  clinicallyReviewed?: boolean;
  available?: boolean;
  reason?: string;
}): ProductTruthPresentation {
  if (input.available === false) {
    return {
      state: "not_available",
      label: PRODUCT_TRUTH_LABELS.not_available,
      reason: input.reason ?? "This result is not available for the current case.",
    };
  }
  if (input.clinicallyReviewed || input.provenance === "clinically_reviewed") {
    return {
      state: "verified",
      label: PRODUCT_TRUTH_LABELS.verified,
      reason: input.reason,
    };
  }
  if (input.fixture || input.experimental || input.provenance === "fixture" || input.provenance === "experimental") {
    return {
      state: "requires_review",
      label: PRODUCT_TRUTH_LABELS.requires_review,
      reason:
        input.reason ??
        "Analysis results need doctor review before they can be treated as clinical identity.",
    };
  }
  if (input.provenance === "generated" || input.provenance === "real") {
    return {
      state: "computed",
      label: PRODUCT_TRUTH_LABELS.computed,
      reason: input.reason ?? "Computed from case geometry. Confirm before clinical use.",
    };
  }
  return {
    state: "requires_review",
    label: PRODUCT_TRUTH_LABELS.requires_review,
    reason: input.reason ?? "Result status requires doctor review.",
  };
}

/** FDI display policy: never invent numbers; show Not Available when absent. */
export function fdiTruthPresentation(fdiNumber: number | null | undefined): ProductTruthPresentation {
  if (fdiNumber == null) {
    return {
      state: "not_available",
      label: PRODUCT_TRUTH_LABELS.not_available,
      reason: "Clinical tooth numbering has not been resolved for this tooth.",
    };
  }
  return {
    state: "requires_review",
    label: PRODUCT_TRUTH_LABELS.requires_review,
    reason: `FDI ${fdiNumber} from analysis — confirm before clinical use.`,
  };
}

/** Forbidden doctor-facing engineering terms (diagnostics may still use these internally). */
export const FORBIDDEN_DOCTOR_TERMS = [
  "Fixture",
  "Experimental",
  "Backend",
  "Worker",
  "Adapter",
  "deterministic planner",
  "ToothInstanceNet",
  "localhost",
] as const;
