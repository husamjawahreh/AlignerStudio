export const DataProvenance = {
  Real: "real",
  Generated: "generated",
  Experimental: "experimental",
  Fixture: "fixture",
  ClinicallyReviewed: "clinically_reviewed",
} as const;

export type DataProvenance = (typeof DataProvenance)[keyof typeof DataProvenance];
