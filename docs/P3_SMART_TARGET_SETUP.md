# P3 Smart Target Setup Engine

## Scope

P3 replaces the previous objective-subset setup behavior with complete,
data-driven deterministic target coverage. It does not implement clinical
approval, biomechanical scoring, or complete staging logic.

## Planning boundary

`TreatmentPlanningEngine` remains the deterministic implementation. The
`PlanningEngineAdapter` protocol in `engines/planning/interface.py` is the port
for future learned or research implementations such as TADPM, STTAlign, or
OrthoAI-style orchestration. Those candidates remain isolated and do not alter
domain contracts.

## Target setup behavior

The planner now creates source/target states for every identified tooth in the
planning input. Explicit objective movements are overlaid only on the tooth
references named by those objectives. All other identified teeth receive an
unchanged target pose with zero movement.

This gives the viewer a complete arch setup without inventing movement values,
FDI identities, or clinical constraints. The target geometry is produced by
the existing local-coordinate rigid transform path and is visible through the
existing real anatomy viewer.

## Proposal summary

The treatment response now includes a review-only `planSummary` with:

- moved tooth count;
- aggregate movement magnitude across proposal dimensions;
- notable conflict warnings;
- data gaps/limitations;
- warning list;
- source provenance (`deterministic planner`); and
- an explicit doctor-review-required flag.

No `AI` label is used because no learned model generated this proposal.

## Known limits

- Existing semantic-only real-artifact flow still supplies one explicit demo
  objective; P3 makes the remaining identified teeth unchanged rather than
  fabricating objectives for them.
- Complete clinical target generation requires authored treatment objectives or
  a separately approved planning engine; it is intentionally not inferred here.
- Staging remains the existing deterministic interpolation engine and is not a
  new P3 feature.
- The proposal remains generated/experimental/fixture-labeled according to the
  source case and always requires doctor review.
