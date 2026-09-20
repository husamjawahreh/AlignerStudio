# Copilot Instructions for AlignerStudio

These rules apply to all AI-assisted contributions in this repository.

## Non-negotiable rules

1. **Do not reuse code from any prior "AlignerStudio" project.** This is a
   clean-room rebuild.
2. **Never invent a clinical threshold.** Every numeric clinical value must
   be added to [CLINICAL_BOUNDARIES.md](../CLINICAL_BOUNDARIES.md) in the
   same change, with a source and status.
3. **Never represent generated/experimental output as clinically
   reviewed.** Use the `DataProvenance` enum (`real | generated |
experimental | clinically_reviewed`) consistently across domain,
   engines, API, and UI.
4. **Placeholder/fixture engines must say so.** Any placeholder
   implementation must set `fixture: true` and a `notes` field explaining
   what is missing. The UI must visibly flag fixture data.
5. **Respect layer boundaries** (see [ARCHITECTURE.md](../ARCHITECTURE.md)):
   - `domain/*` — no imports from `engines/`, `adapters/`, `services/`,
     `apps/`.
   - `engines/*` — may import `domain/*` and their own `adapters/*`
     interface, never a vendor library directly outside of an adapter.
   - `adapters/*` — implement an interface owned by the corresponding
     `engines/*` package; never imported by `domain/` or `apps/web`
     directly.
   - `services/api` — HTTP layer only; translates `packages/contracts`
     DTOs to/from domain entities; calls engines, never adapters directly.
   - `apps/web` — UI only; talks to `services/api` via HTTP.
6. **No circular dependencies.** If you find yourself importing "up" the
   stack, stop and restructure.
7. **No giant files.** Split modules by responsibility; prefer several
   small, well-named files.
8. **Strong typing.** TypeScript must remain `strict`. Python code must use
   type hints and Pydantic models at all boundaries.
9. **External algorithms/models are research references until added to
   [REUSE_MATRIX.md](../REUSE_MATRIX.md).** Never copy external source
   files into this repo. Adapters wrap external libraries/models; they do
   not vendor their code.
10. **Every engine needs tests.** `pytest` for Python engines/domain,
    `vitest` for TypeScript packages/components. Placeholder engines are
    tested too (assert fixture labeling).
11. **Keep clinical rules configurable**, not hard-coded, where they exist.
12. Prefer deterministic algorithms; if a component is stochastic (ML),
    label it clearly and keep it swappable via an adapter interface so it
    doesn't require rewriting callers.

## When implementing a new feature

- Check [TREATMENT_PLAN.md](../TREATMENT_PLAN.md) to confirm which phase it
  belongs to and update the phase table if the status changes.
- Check [CLINICAL_BOUNDARIES.md](../CLINICAL_BOUNDARIES.md) before adding
  any numeric threshold.
- Check [REUSE_MATRIX.md](../REUSE_MATRIX.md) before adding any external
  dependency that implements a clinical algorithm.
- Add/update tests in the same change.
- Do not implement future-phase functionality speculatively — build the
  minimum vertical slice requested and stop for review.
