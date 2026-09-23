# AlignerStudio Project Status Summary

**Date:** 2026-09-23
**Scope:** Research and development status only. No clinical approval or clinical accuracy is claimed.

## Current State

AlignerStudio is a clean-room orthodontic review workspace with a Python/FastAPI backend, React/Three.js frontend, domain models, treatment planning, staging, validation, editing, proposals, and export workflows.

Production remains fail-closed when a real segmentation model is unavailable.

## Segmentation Work

Completed research audits:

- 3DTeethSAM: blocked by CUDA/SAM2/PyTorch3D requirements.
- CrossTooth CVPR2025: blocked by CUDA/pointops; semantic segmentation only.
- Deep model discovery audit: completed for TSegAgent, OrthoGeo3D, TGNet, PMTSeg, THISNet, and related candidates.
- TGNet checkpoint and rights gate: completed; checkpoint available for research only.
- TSegAgent feasibility gate: completed; SAM3 weights are gated and FDI requires an external VLM.
- ToothInstanceNet benchmark/runtime work: completed as a research-only path.

## ToothInstanceNet Backend

An isolated ToothInstanceNet adapter/runtime exists with:

- exact source revision verification;
- checkpoint SHA-256 verification;
- explicit environment-based artifact paths;
- exact six-channel XYZ + normal preprocessing;
- DentalNet/StratifiedTransformer configuration;
- official learned-region clustering;
- official upper-coordinate flip before FDI identification;
- explicit runtime failure states;
- model/FDI diagnostics;
- no automatic fallback or weight download.

A reproducible Docker runtime definition exists for external GPU execution using the validated CUDA/Torch environment. The current development machine cannot run it because Docker, NVIDIA GPU/driver, CUDA, and PyTorch are unavailable.

## Fixture and Pipeline Integration

The existing segmentation pipeline supports explicit ToothInstanceNet fixture selection:

```text
ALIGNERSTUDIO_SEGMENTATION_BACKEND=toothinstancenet_fixture
ALIGNERSTUDIO_TOOTHINSTANCENET_VALIDATED_FIXTURE_DIR=<fixture-directory>
```

Fixture data must explicitly declare:

```text
source_kind = validated_real_case OR development_treatment_fixture
fixture = true
experimental = true
```

There is no automatic fixture fallback.

The temporary smoke fixture remains separate from any validated real-case artifact.

## Viewer Integration

The existing Three.js StageViewer was extended without creating a second renderer. It supports:

- backend-supplied tooth meshes;
- projected FDI labels;
- upper/lower visibility filtering;
- individual tooth visibility;
- raycast selection;
- InspectionPanel metadata;
- provenance and experimental indicators;
- camera fit/reset/orbit/zoom/pan;
- duplicate, missing, and excluded-fragment diagnostics.

## Treatment Planning Integration

The existing treatment engines are reused:

- TreatmentPlanningEngine
- TreatmentStagingEngine
- GeometricValidationEngine
- TreatmentProposalEngine
- TreatmentEditingApplication
- TreatmentSessionStore
- existing treatment API
- existing StageViewer and StageTimeline
- existing export path

A domain-level TreatmentPlanningInput now bridges reviewed tooth identification into treatment planning. Objectives remain explicit; no clinical objectives are invented.

The complete development treatment fixture supports:

```text
Load demo
→ baseline Stage 0
→ Stage 1 / Stage 2 navigation
→ tooth selection
→ explicit edit
→ recalculate
→ updated stages
→ export
```

It is labeled `development_treatment_fixture`, `fixture=true`, and experimental.

## Real-Case Artifact Status

The previously validated 28-tooth real-case ToothInstanceNet artifact is **not present** in the current environment.

No real-case artifact has been fabricated, renamed, or substituted with the smoke fixture.

A Kaggle workflow is prepared to generate and audit the real artifact from actual inference. It requires a Kaggle GPU with the validated runtime and checkpoint.

Prepared tools include:

- real-case Kaggle runner;
- artifact generator;
- independent artifact audit;
- ZIP packaging script;
- Kaggle README and one-cell launcher.

Current status:

```text
REAL ARTIFACT READY FOR KAGGLE EXECUTION — NOT YET GENERATED
```

## Tests and Validation

Latest validation:

- Python tests: **107 passed**
- TypeScript tests: **18 passed**
- TypeScript typecheck: passed
- Frontend production build: passed
- Focused Ruff checks: passed
- Canonical STL hashes unchanged

The full repository Ruff command still reports unrelated pre-existing issues in research benchmark files; touched backend/integration files pass focused Ruff.

## Unchanged Areas

The following remain unchanged by the ToothInstanceNet/treatment work:

- frontend architecture was not replaced;
- treatment planning algorithms were reused, not redesigned;
- staging was reused, not redesigned;
- IPR and export engines were not redesigned;
- existing ONNX segmentation behavior remains the default;
- no live model inference runs in development;
- no GPU dependency was added to the development environment;
- no clinical validation or production deployment claim exists.

## Next Required Step

Run the prepared Kaggle real-case workflow using the actual upper/lower STL files and verified `instseg_full.ckpt`. Then import the audited ZIP through the explicit validated-fixture directory configuration and verify the actual real-case meshes in AlignerStudio.
