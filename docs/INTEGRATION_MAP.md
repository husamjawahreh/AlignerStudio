# Integration Map: External References → AlignerStudio Architecture

**Status:** Planning map only. Nothing described here is implemented yet.
No adapter listed below currently contains real logic — all remain
`NotImplementedError` stubs per [REUSE_MATRIX.md](../REUSE_MATRIX.md). This
map exists so that **when** any of these are implemented in a future phase,
they land in the correct layer on the first attempt.

## How To Read This Map

Each row maps an external reference/concept to the exact AlignerStudio
module that would own it, the interface it must implement, and the gating
condition that must be true before implementation starts.

## Segmentation

| External reference                                                                    | AlignerStudio location                                       | Interface to implement                                                                   | Gate before implementation                                                                                                                                       |
| ------------------------------------------------------------------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| MeshSegNet (code MIT; weights unclear)                                                | `adapters/meshsegnet/adapter.py`                             | `engines/segmentation/interface.py::SegmentationEngine`                                  | Weights license cleared with upstream authors OR replaced with a license-clear alternative; ONNX export completed; add row to `REUSE_MATRIX.md` confirming terms |
| ToothGroupNetwork (no license)                                                        | `adapters/toothgroupnet/adapter.py`                          | `engines/segmentation/interface.py::SegmentationEngine`                                  | **Blocked** — do not implement until an explicit license is added upstream or granted directly; dataset (Teeth3DS+) also blocks commercial training              |
| OpenSourceOrtho's ONNX seam pattern (`load_local_segmenter`)                          | `engines/segmentation/` (new module, e.g. `onnx_backend.py`) | Internal selection logic only — not a public interface change                            | None — this is an architecture pattern to adopt now-independent of any specific model; can be implemented once _any_ license-clear ONNX model exists             |
| OpenSourceOrtho's segmentation quality gates (`reviewable` vs `production candidate`) | `engines/segmentation/quality.py` (new, future)              | Consumed internally by `engines/segmentation` before returning results to `services/api` | None — reasonable to adopt whenever a second (non-placeholder) segmentation backend is added, so the API can label output quality                                |

## Arch Analysis / Coordinate Systems

| External reference                                                    | AlignerStudio location                                                     | Interface to implement                                                                                         | Gate before implementation                                                                                                        |
| --------------------------------------------------------------------- | -------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| OpenSourceOrtho `CoordinateFrame` + `rotation_renderable` pattern     | `domain/tooth/` (extend `Tooth` or add `domain/tooth/coordinate_frame.py`) | New domain value object, no external interface                                                                 | Design-only reuse (concept, not code); add clinical-boundary entry if any numeric axis threshold is introduced                    |
| OpenSourceOrtho arch-form/space analysis (`arch_analysis.py` concept) | `engines/arrangement/` (currently stub)                                    | New `engines/arrangement/interface.py::ArrangementEngine` (does not exist yet — create when this phase starts) | Define `ArrangementEngine` interface first; document any clinical arch-form assumptions in `CLINICAL_BOUNDARIES.md` before coding |

## Planning / Setup Generation

| External reference                                                                                             | AlignerStudio location                                                     | Interface to implement                                                       | Gate before implementation                                                                                                                                 |
| -------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- | ---------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| TANet (arch setup network)                                                                                     | `adapters/tanet/adapter.py`                                                | `engines/planning/interface.py::PlanningEngine`                              | License and exact repository still unconfirmed per `REUSE_MATRIX.md`; must be re-verified before any implementation                                        |
| OpenSourceOrtho's target-resolution priority order (authored → landmark-derived → geometry-derived → template) | `engines/planning/` (new module, e.g. `target_resolution.py`)              | Internal to `engines/planning`, consumed by `PlanningEngine` implementations | Design-only reuse; each new target source must set `DataProvenance` and `fixture` fields consistently with `PlaceholderPlanningEngine`'s existing contract |
| OpenSourceOrtho `MovementCaps`/`AxisCaps`                                                                      | `domain/treatment_plan/models.py` (extend `Stage`/new `MovementCaps` type) | New domain value object                                                      | **Must** add entries to `CLINICAL_BOUNDARIES.md` for every default cap value before merging, per repo rule #2                                              |

## Staging

| External reference                                                | AlignerStudio location                                                                               | Interface to implement                                                                                                                                 | Gate before implementation                                                                                                                                                         |
| ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| OpenSourceOrtho `Stage`/`ToothDelta`/`StageProgressFrame` pattern | `domain/treatment_plan/models.py` (extend `Stage`), `domain/movement/` (new `ToothDelta`-equivalent) | Extends existing `Stage`/`ToothPosition` — no new external interface, but will need `engines/staging/interface.py::StagingEngine` (does not exist yet) | Define `StagingEngine` interface before implementation; keep translation/rotation composition rules (commutative translation, non-composable rotation) explicit like the reference |

## Collision / Proximity Validation

| External reference                                                                           | AlignerStudio location                               | Interface to implement                                                                                       | Gate before implementation                                                                                                         |
| -------------------------------------------------------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| OpenSourceOrtho `collisions.py`/`contact_geometry.py` (informational crown-proximity checks) | `engines/validation/` (currently stub)               | New `engines/validation/interface.py::ValidationEngine` (does not exist yet — create when this phase starts) | Requires real (non-placeholder) segmentation output first, since proximity checks need actual per-tooth geometry, not fixture data |
| OpenSourceOrtho root/bone-aware checks (CBCT-gated)                                          | `engines/validation/root_bone.py` (future, optional) | Same `ValidationEngine` interface, CBCT-gated code path                                                      | Out of scope until a CBCT/DICOM ingestion path exists in AlignerStudio at all (not currently planned)                              |

## IPR / Attachments

| External reference                                             | AlignerStudio location                                                                                                                                 | Interface to implement                                             | Gate before implementation                                                    |
| -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------ | ----------------------------------------------------------------------------- |
| OpenSourceOrtho's IPR-as-metadata pattern (`landmark_plan.py`) | `domain/treatment_plan/` (new first-class `InterproximalReduction` value object — do **not** copy their metadata-bag pattern, see `REUSE_DECISION.md`) | New domain model, consumed by `engines/planning`                   | Add `CLINICAL_BOUNDARIES.md` entry for any IPR amount threshold before coding |
| OpenSourceOrtho's attachment metadata pattern                  | `domain/treatment_plan/` (new first-class `Attachment` value object)                                                                                   | New domain model, consumed by `engines/planning`/`engines/staging` | Same as above                                                                 |

## Export

| External reference                                                    | AlignerStudio location                             | Interface to implement                          | Gate before implementation                                                                                                          |
| --------------------------------------------------------------------- | -------------------------------------------------- | ----------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| OpenSourceOrtho `print-package` (manifest + hashes + zip + proxy STL) | New `engines/export/` package (does not exist yet) | New `engines/export/interface.py::ExportEngine` | Design-only reuse of the manifest/hash pattern; real per-tooth geometry export depends on a real segmentation engine existing first |
| OpenSourceOrtho handoff report (`orthoplan report`)                   | New `services/api` endpoint + `engines/export/`    | Consumes `ExportEngine`                         | Same as above                                                                                                                       |

## Case / Mesh Pipeline

| External reference                                                                          | AlignerStudio location                                                                                                               | Interface to implement                                     | Gate before implementation                                                                                                                                                                               |
| ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| OpenSourceOrtho's metadata-only STL storage + local mesh workspace + unit-confirmation gate | Already partially implemented: `domain/case/models.py::MeshAsset` stores metadata + `file_path`; `services/api` stores files locally | N/A — extend existing `Case`/`MeshAsset`, no new interface | When staging/movement-caps are added, add an explicit **scan-units confirmation** step before any cap is evaluated, mirroring their "units default to unverified" rule — add to `CLINICAL_BOUNDARIES.md` |
| OpenSourceOrtho's `CaseStore`/`PlanVersion` content-hashed snapshots                        | New `services/api/app/store.py` extension or `domain/case/` versioning module                                                        | N/A                                                        | Needed for "Modify → Recalculate" phase (not yet scheduled)                                                                                                                                              |

## Summary of New Interfaces This Map Anticipates (None Exist Yet)

These interfaces are named here for future consistency but are **not
created in this change**:

- `engines/arrangement/interface.py::ArrangementEngine`
- `engines/staging/interface.py::StagingEngine`
- `engines/validation/interface.py::ValidationEngine`
- `engines/export/interface.py::ExportEngine` (new package)

Each should follow the existing pattern in `engines/segmentation/interface.py`
and `engines/planning/interface.py`: a `Protocol`, a `Placeholder*Engine`
fixture implementation tagged `generated`/`fixture=True`, and matching tests,
before any real (adapter-backed) implementation is attempted.
