# PRE-FIRST-VERSION — Command 01 Segmentation Audit

**Date:** 2026-09-26  
**Command:** PRE-FIRST-VERSION Command 01 (deep root-cause audit)  
**Verdict:** **PASS WITH BLOCKER**  
**Scope:** Evidence only. No segmentation rewrite, no UI redesign, no WP-14, no WP-15.

This audit does not claim the product is world-class.

`Aligner_Studio_First_Version_World_Class_Plan.md` is cited by later WP docs but is **not present** in this repository. The authoritative gate is `PRE_FIRST_VERSION_WORLD_CLASS_GATE.md`. Related docs read: `AlignerStudio_PRODUCTION_MASTER_PLAN_v2.1.md`, `docs/FV01_PRODUCT_REALITY_AUDIT.md`, `docs/FV01_DEPENDENCY_MATRIX.md`, `docs/WP10_PRODUCTION_CAD.md`, `docs/WP11_WORLD_CLASS_UX.md`, `docs/WP12_PERFORMANCE.md`, `docs/WP13_RELIABILITY.md`.

---

## 1. Executive finding

The strings the UI showed —

`Uploaded mesh SHA-256 does not match verified artifact lower.stl`  
`Test-fixture processing refuses silent substitution`

— are raised in **one place only**: `adapters/toothinstancenet/fixture.py` `load_validated_fixture`, and only when processing is on the **TEST_FIXTURE** path (`ALIGNERSTUDIO_SEGMENTATION_BACKEND=toothinstancenet_fixture` plus the allow flag) **and** the uploaded file bytes are not identical to the verified artifact `{arch}.stl`.

That is fail-closed behavior, not silent substitution. It is also **not** a REAL_CASE hash bug. REAL_CASE never compares the upload to the verified artifact.

The clinical consequence (Segmentation Failed, 0 / 0 / 0 teeth, Treatment Setup unavailable) follows because the fixture loader raises, the diagnostic state becomes `segmentation_failed`, and no tooth instances are written.

Live ToothInstanceNet inference was **not invoked** on this host. Default backend is `onnx`. Checkpoint and source revision are present and match the contract, but torch, pointops, NVIDIA driver, nvcc, and Docker are missing. Live inference is **BLOCKED BY ENVIRONMENT**.

The ~17–18 minute “Review Treatment Setup” wait is dual-arch geometric validation inside session compose (`Evaluating collisions and proximity`), not treatment-setup or staging math. WP-12 isolation keeps the API responsive; it does not shrink that CPU wall time.

---

## 2. Real pipeline map

```text
UPLOAD
  cases.py upload_mesh
  bytes → {UPLOAD_DIR}/{case_id}-{arch}-{uuid}.stl
  Case.add_mesh(MeshAsset) → case store (cases.json)
  No SHA-256 at upload time.

INPUT BYTES / HASH
  processing.py compute_case_input_hash
  job input_hash = SHA-256(case_id + sorted arch paths + per-file SHA-256)
  Per-arch source_mesh_sha256 computed later (real path or fixture bind).

STORAGE / CASE RECORD
  InMemoryCaseStore + ALIGNERSTUDIO_CASE_STORE
  Mesh path, arch, case_id persisted with the case.

PROCESSING JOB
  POST /cases/{id}/processing → processing.start_processing → _run
  Stages: PREPARING → VALIDATING_SCANS → SEGMENTING_UPPER/LOWER
          → BUILDING_PLAN → VALIDATING_PLAN → FINALIZING
  Alternate analysis path: POST /cases/{id}/pipeline/{arch}
  → pipeline_diagnostics.process_uploaded_case

MODE BOUNDARY  ← first divergence for the observed hash strings
  processing_modes.resolve_processing_mode
  Default backend: onnx → REAL_CASE
  toothinstancenet_fixture without allow flag → ProcessingModeError → MODEL_UNAVAILABLE
  toothinstancenet_fixture + ALIGNERSTUDIO_ALLOW_TEST_FIXTURE_BACKEND=1 → TEST_FIXTURE

REAL_CASE
  real_case_pipeline.process_real_uploaded_arch
  require_real_case_mode() refuses fixture backend
  source_mesh_sha256 = sha256(uploaded file)  (provenance only; not compared to artifact)
  backend toothinstancenet → ToothInstanceNetEngine.segment(uploaded path)
  else → ONNX configuration path
  Notes explicitly: no fixture substitution

TEST_FIXTURE
  load_validated_fixture_result(arch, source_mesh_path)
  sha256(upload) must equal SHA256SUMS {arch}.stl
  mismatch → ToothInstanceNetFixtureError (the two UI strings)
  match → reconstruct instances from artifact JSON/STL (geometry source is the artifact)

PREPROCESS / INFERENCE (live model only)
  engines/segmentation/toothinstancenet.py ToothInstanceNetEngine.segment
  adapters/toothinstancenet/preprocessing.py prepare_mesh
  adapters/toothinstancenet/adapter.py ToothInstanceNetAdapter.infer

POSTPROCESS / IDENTITY
  ToothInstance meshes; tooth_ref = {arch}:instance:{id}
  Optional FDI only via verified class mapping; fixture path sets fixture=True
  Never invent FDI when identification is incomplete

PERSISTENCE
  segmentation_store begin / store_arch_result / complete_segmentation_record
  On failed states: status=failed, error=joined failures
  On success: dental intelligence stored; session composed later

ANALYSIS API / UI
  diagnostic.state → analysisPresentation stateLabel ("segmentation failed")
  Detected/Upper/Lower counts from tooth meshes (0 when instances were not produced)
  diagnostic.failures rendered as analysis findings

REVIEW TREATMENT SETUP
  App.handleGeneratePlan → POST /processing (full job, not a lightweight open)
  Session _compose → staging → GeometricValidationEngine (cache miss on first plan)
```

| Boundary | Identity carried |
|---|---|
| Upload | `case_id`, arch, stored path. No hash yet. |
| Job | `job_id`, `input_hash` |
| REAL_CASE | `source_mesh_sha256`, `processing_mode=real_case`, `fixture=false`, model name/version when inference runs |
| TEST_FIXTURE | upload hash bound to artifact `{arch}.stl`; `source_kind=validated_real_case`; `fixture=true` |
| Failure | `segmentation_failed` or `model_unavailable`; error text persisted; no fixture fallback |

---

## 3. Exact hash / artifact investigation

**Only raise site** (`adapters/toothinstancenet/fixture.py`, cache-hit and cold path):

- Cache path: uploaded hash vs `checksums[f"{arch}.stl"]` (about lines 288–296).
- Cold path: uploaded hash vs `source_stl_sha256` (about lines 308–314).
- Message includes both observed sentences.

**Propagation:**

1. `pipeline_diagnostics.process_uploaded_case` catches the exception and returns `PipelineState.SEGMENTATION_FAILED` with `failures=(str(error),)` (about lines 133–138).
2. `processing._run` treats `segmentation_failed` as fatal, calls `complete_segmentation_record(..., status="failed")`, and raises `ValueError` with the joined failure text (about lines 523–536).
3. The job `_fail` path stores that exception string (about lines 649–657).
4. Analysis UI: `buildAnalysisOverview` sets `stateLabel` from `diagnostic.state` (`analysisPresentation.ts`). Counts come from tooth meshes (`AnalysisPanel.tsx`). Findings include `diagnostic.failures` (`analysisPresentation.ts`).

**What was ruled out (no evidence they are the first divergence):**

| Hypothesis | Result |
|---|---|
| Wrong artifact mapping inside REAL_CASE | REAL_CASE does not select verified artifact STLs |
| Stale upload hash vs normalized bytes | Hash is of the uploaded file before model preprocess. Normalization is inside `prepare_mesh`, after the fixture gate, and only on the live-model path |
| Fixture accidentally used as REAL_CASE success | `require_real_case_mode` and tests refuse it |
| Official artifact checksums corrupt | On-disk hashes match `SHA256SUMS.txt` exactly (section 5) |

**First divergence:** the TEST_FIXTURE identity gate. The uploaded lower mesh was not byte-identical to verified `lower.stl` (`5cb38bd65cb2a9f04c89c580774e2d6c4ed28582fb46cc160fdc1249020feec3`). The loader refused to substitute artifact geometry.

WP-11 browser QA is a **different** run: it uploaded the official STLs under `toothinstancenet_fixture` and completed with 28 teeth (`.research/tmp/wp11_browser_qa/evidence.json`). That does not contradict this failure. Matching bytes pass the gate; other bytes fail it.

---

## 4. ToothInstanceNet runtime audit

| Item | Verified value |
|---|---|
| Model | `toothinstancenet` / DentalNet (`teethland.models.dentalnet.DentalNet`) |
| Version | `3dteethland-424252e3d94a1565c8c2090eb5bb456b76386b93` (`adapters/toothinstancenet/contract.py`) |
| Checkpoint SHA-256 | `100c68a9b120402cc75539eff6347bd998bce8b1d4f01550638f471797d70803` |
| Checkpoint on disk | `~/.cache/alignerstudio-research/toothinstancenet/checkpoints/instseg_full.ckpt` (111,127,353 bytes). SHA **matches**. |
| Source HEAD | `424252e3d94a1565c8c2090eb5bb456b76386b93`. **Matches**. |
| Load | `verify_checkpoint` → import torch / DentalNet / pointops → `torch.load` → `load_state_dict` |
| Input | STL/PLY/OBJ triangle mesh; z-score (`std=17.3281`), pose normalize, voxel downsample 0.025; XYZ+normals |
| Output | Per-vertex instance and 7-class labels; domain engine builds `ToothInstance` meshes |
| Device | Adapter `auto` prefers CUDA; acceptance runtime **requires** CUDA. No proven CPU fallback (pointops is a CUDA extension). |
| Default API backend | `onnx` (`processing_modes.selected_backend`). Live model runs only when `ALIGNERSTUDIO_SEGMENTATION_BACKEND=toothinstancenet`. |
| Invoked this audit | **No.** No `ALIGNERSTUDIO_*` segmentation env vars set. `import torch` and `import pointops` fail. |

**Failure modes (unchanged):** missing checkpoint/source/torch → `MODEL_UNAVAILABLE`; inference exception → `SEGMENTATION_FAILED`; both state that no fixture substitution was performed (`real_case_pipeline.py`).

Documented timing/memory hooks exist (`clustering_and_fdi_seconds`, `peak_gpu_memory_bytes`) but **no successful live inference numbers** exist for this host. Prior acceptance status remains blocked (`docs/SEGMENTATION_TOOTHINSTANCENET_BENCHMARK.md`, `research/benchmark/toothinstancenet/runtime/README.md`).

---

## 5. Official real-case audit

Artifact: `.research/tmp/official_real_case_stage2_verified_v1`  
Not modified.

| File | SHA-256 (matches SHA256SUMS) | Size |
|---|---|---|
| `lower.stl` | `5cb38bd65cb2a9f04c89c580774e2d6c4ed28582fb46cc160fdc1249020feec3` | 6,954,234 bytes |
| `upper.stl` | `96e23a65e6a0eaa5550704be628dd3d27c6c5813213f6ea6b48b386d5178bd1e` | 8,557,034 bytes |
| `lower.json` | `f42ec3685492e61d80c2a7b813c287d7e554cd8be6f537a31233f8ff793cb5f6` | 500,662 |
| `upper.json` | `eb9841ca59ca58d77fdc14f9fbc2a9ebec26b272e8a7b91a2895d3b1a61b8e09` | 622,998 |

Mesh check (`trimesh` 5.1.0, `process=False`):

| Arch | Vertices | Faces | Watertight | Format |
|---|---|---|---|---|
| lower | 417,249 | 139,083 | no | binary STL (80-byte header starts `COLOR=`) |
| upper | 513,417 | 171,139 | no | binary STL (same header style) |

Non-watertight crowns are expected for intraoral scans. This is not an artifact checksum defect.

Manifest (`manifest.json`): stage `instances`, 7-class config (`distinguish_left_right=false`, `distinguish_upper_lower=false`), semantic audit **pass** with 14 instances per arch. Explicitly **not** a clinical 28-tooth FDI accuracy claim (`clinical_accuracy_claim: false`).

Artifact inconsistency vs application defect: **none found** in checksums or mesh load. The clinical limitation (7-class labels, not verified FDI) is declared by the artifact itself and must stay declared.

---

## 6. Segmentation failure state flow

| Step | Owner | Effect |
|---|---|---|
| Set pipeline state | `process_uploaded_case` / `process_real_uploaded_arch` | `segmentation_failed` or `model_unavailable` |
| Counts | Diagnostic `tooth_instance_count` and UI tooth list | 0 when no instances returned |
| Persist failure | `processing._run` → `complete_segmentation_record(status="failed")` | Error string stored on the case segmentation record |
| Expose to UI | Pipeline payload `state` + `failures`; job `_fail` detail | Analysis state label `segmentation failed`; findings show the hash text on the fixture path |
| Recoverable? | Yes as a **new** job after a failed/interrupted job | WP-13: no mid-stage resume |
| Stale state | Restart mid-`PROCESSING` becomes `INTERRUPTED` and demotes in-flight segmentation (`docs/WP13_RELIABILITY.md`) | A new attempt gets a new `job_id`. Failed records are not rewritten into success. |
| UI freshness | Analysis renders the diagnostic returned by the last pipeline call | A failed diagnostic with empty teeth is current for that attempt, not a hidden success |

WP-13 semantics were **not** changed. Interruption matrix evidence remains `.research/tmp/wp13_reliability/interruption_matrix.json` (11/11 PASS, prior WP). Cancel, interrupted, and failed stay distinct. This audit did not re-run the interruption matrix script.

---

## 7. Review Treatment Setup performance trace

**UI:** label `Review Treatment Setup` (`workflow.ts`, `CaseIntakePanel.tsx`, `TreatmentSetupPanel.tsx`).  
**Handler:** `App.handleContextualAction` → `handleGeneratePlan`.  
**Non-test behavior:** busy copy `Starting case analysis`, then `api.startProcessing` → `POST /cases/{id}/processing`. This is a full processing job, not “open an existing plan.”

**Inside the job, after segmentation:** `TreatmentSessionStore._compose` (`treatment_sessions.py`):

1. `Preparing geometric validation` (progress 72) — `TreatmentStagingEngine.generate`
2. `Evaluating collisions and proximity` (progress 82)
3. `get_cached_report` — **miss** on a new `plan_id` / `staging_id`
4. `validate_staging` → process-isolated `GeometricValidationEngine.validate`
5. `store_cached_report`, then session persist

**Why ~17 minutes:**

| Work | Evidence | Role |
|---|---|---|
| Dual-arch geometric validation | WP-11: ~18 m at “Evaluating collisions” (`.research/tmp/wp11_browser_qa/evidence.json` notes; `docs/WP11_WORLD_CLASS_UX.md`) | Dominant |
| Upper-only cold validate | WP-12: **214.5 s** in-process (`docs/WP12_PERFORMANCE.md`) | Same engine, one arch |
| Treatment setup / staging | WP-12: ~1.4 s / ~1.5 s | Not the bottleneck |
| Report cache | Hit only when staging id + thresholds match | First Review is a miss |
| Process isolation | Default on (WP-12) | API stays responsive; CPU time unchanged |
| Production CAD | Not on this path | Not the 17 minutes |
| Re-segmentation | Review starts full `POST /processing` even after Analyze | Extra work, seconds-to-small vs validation |

This is legitimate expensive computation under current clinical semantics (a persisted session includes a geometric validation report), plus a workflow issue: the button name says “review” while the production path recomputes the whole job. Semantics were not changed in this command.

---

## 8. Current UI architecture assessment

No redesign was performed.

| Problem | Where |
|---|---|
| Duplicate Status | Case intake left and right (`CaseIntakePanel.tsx`); header pill and bottom status (`App.tsx`); Validation “Review Status” stack |
| Duplicate Data Readiness | Intake readiness, Analysis capability readiness, viewport chrome, Treatment Setup readiness matrix |
| Duplicate Processing | Intake processing rows plus fullscreen loading overlay from the same status |
| Duplicate actions | Analyze / Review Treatment Setup on contextual strip and step panels; export, arch visibility, current/target, and stage transport repeated |
| Left-panel scrolling | One `.cad-panel` scroller holds step content plus viewport chrome; Analysis still stacks engineering sections in the primary column |
| Right-panel clipping | Fixed inspector width (~292px), `overflow: auto`; refinement stacks proposal + inspection in that rail |
| Unnecessary badges | Workspace-ready pill, fixture/truth badges, experimental provenance badge |
| Notifications | Repeated review notes; errors in the left rail and overlay |
| Technical data in primary workflow | Mesh QA, capability matrices, confidence to 3 decimals, version id slices, raw freshness enums still at level 1 in Analysis / Setup / Validation |
| Analyze vs Review Treatment Setup | Analyze → `handleReviewSegmentation` → `POST /pipeline/{arch}` with busy text “Reviewing segmentation”. Review Treatment Setup → `startProcessing` with busy text “Starting case analysis”. Three different verbs for overlapping heavy work. |
| Viewport constraint | Fixed left ~252px and right ~292px rails plus optional timeline; 3D is center but never full-bleed |

---

## 9. Current 3D presentation assessment

`StageViewer` already separates presentation from clinical geometry:

- Materials, ACES lighting, soft shadows, and gingiva translucency live in `materialProfiles.ts` / `StageViewer.tsx` and are marked presentation-only.
- Synthetic gingiva (`syntheticGingiva.ts`) sets `presentationOnly` and `clinicalGeometry: false`, is not on the tooth pick list, and is excluded by `isClinicalGeometryOverlay`. It is not imported by analysis, validation, staging, or export. **Confirmed: synthetic gingiva cannot enter clinical calculations.**
- Labels, selection, current/target ghosts, arch filter, and validation colors exist, but tooth/gingiva shading is not a premium clinical first impression.
- Official artifact identity is 7-class / `tooth_ref`, not verified FDI. The viewer must not present fabricated numbering.

Presentation geometry was not replaced.

---

## 10. Technology evaluation

No production model was replaced. Classifications for this gate:

| Technology | Decision | Why |
|---|---|---|
| ToothInstanceNet / 3dteethland | **ADAPTER (baseline)** | Closest existing contract (STL → instances). Checkpoint and source verified. Live path not runnable here. Do not replace before a real-case benchmark. |
| 3DTeethSAM | **EVALUATE** | Public checkpoint and instance-segmentation direction (`docs/SEGMENTATION_MODEL_FINAL_SHORTLIST.md`, `docs/SEGMENTATION_3DTEETHSAM_BENCHMARK.md`). Prior benchmark **BLOCKED** on GPU/PyTorch3D/SAM2. Heavier adapter; FDI contract weaker than ToothInstanceNet. Not a silent fallback. |
| DentalModelSeg (SlicerDentalModelSeg / Fly-by-CNN, DCBIA-OrthoLab) | **EVALUATE** | 3D Slicer multi-view crown segmentation with FDI/Universal labeling ([SlicerDentalModelSeg](https://github.com/DCBIA-OrthoLab/SlicerDentalModelSeg/), [paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC10949221/)). Slicer/VTK runtime is outside the API stack. No AlignerStudio benchmark yet. |
| Slicer Automated Dental Tools / ALI-IOS | **REFERENCE** | Landmark and orientation concepts only (`docs/WORLD_CLASS_OPEN_SOURCE_ADOPTION_MATRIX.md`). License must be checked per component before any adapter. |
| MeshSegNet | **REFERENCE** | Already measured; fragmented semantic masks and decimation. Not an instance/FDI contract. |
| React Three Fiber / Drei | **REFERENCE** | Would rewrite a working `StageViewer` without a measured defect that requires it. |
| three-mesh-bvh | **EVALUATE** | Possible picking/proximity adapter later. Not justified by this audit. |
| Manifold (WP-10 production geometry) | **ADOPT (already)** | Leave in place. Not part of segmentation. |

---

## 11. Confirmed blockers

1. TEST_FIXTURE cannot segment an upload that is not byte-identical to the official artifact. That failure is correct and must stay. It is the wrong backend for arbitrary real scans.
2. Live REAL_CASE ToothInstanceNet cannot run in this environment (section 12).
3. Default backend is ONNX, which is also unavailable without a configured model (`MODEL_UNAVAILABLE`, no fixture fallback).
4. Official artifact does not provide clinical FDI. Do not fabricate it.
5. First “Review Treatment Setup” pays full dual-arch geometric validation (~18 minutes observed).
6. UI duplicates status/readiness/actions and mislabels Analyze vs Treatment Setup. Architecture only; not fixed here.
7. 3D tooth/gingiva presentation is not yet a professional clinical first screen.

---

## 12. Environment blockers

Checked 2026-09-26 on this host. **BLOCKED BY ENVIRONMENT** for live inference.

| Requirement | Result |
|---|---|
| `ALIGNERSTUDIO_SEGMENTATION_BACKEND` and related vars | Unset |
| NVIDIA driver (`nvidia-smi`) | Fails: cannot communicate with the NVIDIA driver |
| `nvcc` | Not found |
| Docker | Not found |
| Python | 3.12.3 (project `.venv` and system) |
| `torch` | `ModuleNotFoundError` (system and `.venv`) |
| `pointops` | `ModuleNotFoundError` |
| Checkpoint + source revision | Present and match contract |

Do not substitute fixture inference to clear this blocker.

---

## 13. Recommended implementation order

Unchanged from the gate, with Command 01 evidence applied:

1. **Wave 1 — Real segmentation recovery.** Run REAL_CASE on the uploaded mesh. Enable ToothInstanceNet only when CUDA/torch/pointops exist. If they do not, stop with the environment blocker. Do not point arbitrary uploads at the fixture loader to “pass.”
2. Wave 2 — Benchmark ToothInstanceNet against 3DTeethSAM / DentalModelSeg on real cases before any replacement.
3. Waves 3–4 — Clinical segmentation review and premium 3D, after real instances exist.
4. Waves 5–7 — UI architecture (one status, one readiness, Analyze vs Treatment Plan) and honest remaining-time around geometric validation.
5. Later waves, then WP-14, then WP-15. Not now.

---

## 14. What MUST NOT be changed

- REAL_CASE must stay real. No silent TEST_FIXTURE substitution.
- Do not fabricate FDI, tooth identity, or segmentation.
- Do not weaken the fixture hash gate, GeometricValidationEngine, Validation 2.0, WP-12 isolation/cache, or WP-13 interrupted/cancelled/failed semantics.
- Do not replace ToothInstanceNet before a measured benchmark.
- Do not delete existing tests or rewrite completed WP implementations to hide this failure.
- Do not start WP-14 or WP-15.
- Synthetic gingiva stays presentation-only.
- Official artifact files stay unmodified.

---

## Tests run

| Suite | Result |
|---|---|
| `tests/python/test_toothinstancenet_fixture.py` | Included in 28 passed |
| `tests/python/test_toothinstancenet_artifact_identity.py` | Included in 28 passed |
| `tests/python/test_wp01_real_clinical_pipeline.py` | Included in 28 passed |
| Combined above | **28 passed**, 6.61 s |
| `tests/python/test_wp12_performance.py` | Included in 15 passed |
| `tests/python/test_wp13_reliability.py` | Included in 15 passed |
| Combined above | **15 passed**, 12.77 s |
| Live ToothInstanceNet acceptance | **BLOCKED BY ENVIRONMENT** (not executed; fixture not used as a substitute) |

Tests were not modified.

Typecheck, lint, and production build were **not** re-run. This command changed documentation only.

---

## Explicit stop

- WP-14 desktop packaging: **NOT STARTED**
- WP-15 final real-case gate: **NOT STARTED**
- Segmentation rewrite: **NOT STARTED**
- World-class UI implementation: **NOT STARTED**

---

# WAVE 1 IMPLEMENTATION RESULT

**Date:** 2026-09-26  
**Verdict:** **PASS WITH BLOCKER**  
**Real inference executed:** **No.**

The production REAL_CASE path is explicit and fail-closed. This host still cannot run ToothInstanceNet. Fixture geometry was not used as evidence.

## Exact code changes

- `services/api/app/segmentation_runtime.py` — runtime capability probe. Never selects TEST_FIXTURE.
- `services/api/app/real_case_pipeline.py` — attaches source inspection, backend, truth state, and blocker. Source STL bytes are not rewritten.
- `services/api/app/pipeline_diagnostics.py` — `blocked_by_environment` state plus provenance fields on the diagnostic.
- `services/api/app/processing.py` — `SEGMENTATION_FAILURE_STATES` includes `blocked_by_environment`, so that outcome stays a durable FAILED job. Cancel and INTERRUPTED behavior were not rewritten.
- `apps/web/src/analysisPresentation.ts` and `AnalysisPanel.tsx` — a blocked or failed run shows **Blocked by environment** or **Failed**, and tooth counts show **Not available** instead of a clinical 0.
- `tests/python/test_wave1_real_segmentation_recovery.py` — new tests. Existing tests were not weakened.

Tooth instance mapping in `engines/segmentation/toothinstancenet.py` was not rewritten. One non-negative instance id still becomes one mesh. Seven-class labels stay model output with `requires_review` when identification is incomplete. FDI is not invented on the blocked path (`tooth_instances` is empty).

## Real backend behavior

| Backend | When | Result on this host |
|---|---|---|
| `onnx` (default) | `ALIGNERSTUDIO_SEGMENTATION_BACKEND` unset | `model_unavailable` with `segmentation_truth_state=blocked_by_environment` |
| `toothinstancenet` | explicit | `blocked_by_environment` |
| `toothinstancenet_fixture` | only with `ALIGNERSTUDIO_ALLOW_TEST_FIXTURE_BACKEND=1` | TEST_FIXTURE. Otherwise rejected. |

ONNX is not a working production segmenter here. The adapter expects an external MeshSegNet ONNX file plus a contract (`ALIGNERSTUDIO_SEGMENTATION_MODEL` and `ALIGNERSTUDIO_SEGMENTATION_CONTRACT`). No weights are in the repository. Input is one per-face feature tensor. Provider coded in the adapter: `CPUExecutionProvider` only. It does not emit ToothInstanceNet instances, and no new adapter was invented.

## Model / runtime status

ToothInstanceNet still requires a GPU path:

- NVIDIA driver visible to `nvidia-smi`
- CUDA compatible with compiled `pointops`
- PyTorch (validated research image: 2.10.0+cu128 / CUDA 12.8; upstream docs also cite 2.3.0 / CUDA 12.1)
- `pointops`
- checkpoint `instseg_full.ckpt` SHA-256 `100c68a9b120402cc75539eff6347bd998bce8b1d4f01550638f471797d70803`
- source `424252e3d94a1565c8c2090eb5bb456b76386b93`
- `ALIGNERSTUDIO_TOOTHINSTANCENET_CHECKPOINT` and `ALIGNERSTUDIO_TOOTHINSTANCENET_SOURCE`

CPU inference is **not** supported. The checkpoint cache file can exist on disk and still be unused until those variables and the GPU stack are present.

## Real-case result

`official_real_case_stage2_verified_v1` was run through `process_uploaded_case` on the default ONNX REAL_CASE path.

| Arch | SHA-256 unchanged | Vertices | Faces | Instances | State |
|---|---|---|---|---|---|
| upper | `96e23a65e6a0eaa5550704be628dd3d27c6c5813213f6ea6b48b386d5178bd1e` | 513417 | 171139 | 0 | blocked (model unavailable / blocked_by_environment) |
| lower | `5cb38bd65cb2a9f04c89c580774e2d6c4ed28582fb46cc160fdc1249020feec3` | 417249 | 139083 | 0 | blocked (model unavailable / blocked_by_environment) |

`source_bytes_modified` is false. Units stay `unverified`. Coordinate system recorded as `source_file_coordinates`. No FDI. No fixture flag.

## Remaining blocker

**BLOCKED BY ENVIRONMENT.** Missing NVIDIA driver, torch, pointops, nvcc, and Docker. Default ONNX weights are also absent. Do not treat this as a successful segmentation.

## Provenance behavior

Every real diagnostic carries `case_id` / `job_id` when the caller supplies them, `arch`, `backend`, `source_mesh_sha256`, `input_hash`, `preprocessing`, `runtime`, and `segmentation_truth_state`. A failed record stored through the segmentation store keeps those fields and `status=failed`. Cancellation remains `CANCELLED`. Process restart remains `INTERRUPTED` / segmentation `interrupted`.

## Tests (Wave 1)

| Suite | Result |
|---|---|
| `tests/python/test_wave1_real_segmentation_recovery.py` plus WP-01, API cases, ToothInstanceNet pipeline, WP-12, WP-13 | **50 passed**, 39.75 s |
| `apps/web` `analysisPresentation.test.ts` | **5 passed** |
| `apps/web` `App.test.tsx` | **6 passed** |
| `tsc --noEmit` | pass |
| `eslint` on the touched web files | pass |
| `npm run build` | pass (existing chunk-size warning only) |
| Live ToothInstanceNet inference | **not run** |

## Not started

Premium UI, segmentation review workspace, new materials, gingiva presentation, contextual toolbar, workflow redesign, WP-14, and WP-15 were not started.
