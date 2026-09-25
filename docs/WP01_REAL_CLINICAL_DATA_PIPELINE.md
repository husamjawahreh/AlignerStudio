# WP-01 — Real Clinical Data Pipeline

**Work package:** FIRST VERSION WP-01  
**Date:** 2026-09-25  
**Authoritative roadmap:** `AlignerStudio_PRODUCTION_MASTER_PLAN_v2.1.md`  
**Starting point:** FV-01 Product Reality Audit  
**Scope:** Real uploaded STL → genuine ToothInstanceNet path. **WP-02 and WP-03 were NOT started.**

---

## 1. WP-01 verdict

**PASS with an environment blocker for live GPU inference.**

- Silent fixture substitution is **removed from the production real-case path**.
- An explicit **REAL_CASE vs TEST_FIXTURE** boundary is enforced.
- Uploaded mesh path + SHA-256 + job identity + input_hash are bound into processing and persistence.
- When real ToothInstanceNet cannot run, the failure is preserved — **no fixture fallback**.
- Live CUDA ToothInstanceNet could not be executed end-to-end in this environment (no `torch` in `.venv`, no NVIDIA driver). That is documented as a blocker, not hidden.

This is **not** world-class / doctor-ready / production-ready / complete.

---

## 2. Exact fixture substitution root cause

**Where:**

1. `services/api/app/pipeline_diagnostics.py` — when `ALIGNERSTUDIO_SEGMENTATION_BACKEND=toothinstancenet_fixture`, `process_uploaded_case(mesh_path, …)` called `load_validated_fixture_result(arch, mesh_path)` which **ignored upload bytes** and reconstructed geometry from the verified artifact ZIP/DIR.
2. `services/api/app/routers/cases.py` — `generate_plan_with_progress` called `_combined_fixture_identification()` whenever the fixture backend was selected, **without using case uploads**.
3. `services/api/app/processing.py` — required both arches to be `identification_incomplete` (fixture-shaped) and then called the fixture-only plan path.

**Effect:** A doctor upload could appear “processed” while the UI/session showed artifact geometry unrelated to the uploaded STL hash.

---

## 3. Exact production-path change

| Boundary | Behavior |
|---|---|
| `REAL_CASE` | Default for non-fixture backends. Always `ToothInstanceNetEngine.segment(uploaded_path)` or ONNX on the uploaded path. Fixture loader never called. |
| `TEST_FIXTURE` | Only when `ALIGNERSTUDIO_SEGMENTATION_BACKEND=toothinstancenet_fixture` **and** `ALIGNERSTUDIO_ALLOW_TEST_FIXTURE_BACKEND=1`. |
| Fixture without allow | `ProcessingModeError` / `MODEL_UNAVAILABLE` — blocked. |
| Hash binding | Fixture loader requires uploaded SHA-256 == artifact `{arch}.stl` when `source_mesh_path` is provided. |
| Persistence | `case.segmentation_results` stores job_id, input_hash, mode, model name/version, per-arch payloads, timings. |
| Plan | Processing builds plan from **pipeline diagnostics of the uploaded run**, not from a detached fixture reload. HTTP `/plan` prefers persisted completed segmentation; fixture plan only in TEST_FIXTURE mode. |

---

## 4. Real-case runtime path before

```text
UPLOAD STL (stored under data/uploads)
 → start_processing
 → process_uploaded_case
 → [if backend=toothinstancenet_fixture] load_validated_fixture(ARTIFACT)  ← IGNORE UPLOAD
 → generate_plan_with_progress → _combined_fixture_identification()      ← IGNORE UPLOAD AGAIN
 → treatment session / browser DTO from fixture geometry
```

---

## 5. Real-case runtime path after

```text
UPLOAD STL (stored; content hashed into job input_hash)
 → start_processing (new job_id, input_hash, heartbeat)
 → resolve_processing_mode()
      REAL_CASE → process_real_uploaded_arch(uploaded_path)
                   → ToothInstanceNetEngine.segment(uploaded_path)  [or ONNX]
                   → bind source_mesh_sha256 / case_id / job_id / input_hash
                   → persist segmentation_results[arch]
                   → on failure: FAILED (no fixture)
      TEST_FIXTURE (explicit allow only)
                   → load_validated_fixture with hash binding to upload
 → generate_plan_from_arch_diagnostics(persisted/real results)
 → treatment session / browser DTO from that bound result
```

---

## 6. Files changed

### New
- `services/api/app/processing_modes.py`
- `services/api/app/real_case_pipeline.py`
- `services/api/app/segmentation_store.py`
- `services/api/app/plan_from_pipeline.py`
- `tests/python/test_wp01_real_clinical_pipeline.py`
- `docs/WP01_REAL_CLINICAL_DATA_PIPELINE.md` (this file)

### Modified
- `services/api/app/pipeline_diagnostics.py`
- `services/api/app/processing.py`
- `services/api/app/routers/cases.py`
- `services/api/app/store.py`
- `services/api/app/toothinstancenet_configuration.py`
- `adapters/toothinstancenet/fixture.py` (source-mesh hash binding)
- Existing fixture-using tests (+ `ALIGNERSTUDIO_ALLOW_TEST_FIXTURE_BACKEND=1`)

---

## 7. Model used

- **Baseline:** ToothInstanceNet (`instseg_full` / DentalNet) — **not replaced**
- **Not integrated:** 3DTeethSAM
- Checkpoint present on machine (not in repo):  
  `/home/hjawahreh/.cache/alignerstudio-research/toothinstancenet/checkpoints/instseg_full.ckpt`  
  Expected SHA-256: `100c68a9b120402cc75539eff6347bd998bce8b1d4f01550638f471797d70803`
- Source revision present: `424252e3d94a1565c8c2090eb5bb456b76386b93`

---

## 8. Input artifact / hash evidence

| Item | Value |
|---|---|
| Official ZIP | `official_real_case_stage2_verified_v1.zip` |
| ZIP SHA-256 | `b0f57d45e19ec1c981964dcad1309570fdc96ec21052ada62050fa3ccb8621b2` |
| Extracted STLs used in WP-01 tests | `.research/tmp/official_real_case_stage2_verified_v1/{upper,lower}.stl` |
| Job `input_hash` | SHA-256 over case_id + per-arch path + file digests (`compute_case_input_hash`) |
| Per-arch `source_mesh_sha256` | Stored on diagnostic + segmentation record |

---

## 9. Job lifecycle evidence

Preserved/extended from FV-01:

- New attempt after FAILED → **new `job_id`**, progress resets to 0 / PREPARING
- Duplicate in-flight → same job_id
- Stale heartbeat → STALE (distinct identity required on retry)
- Segmentation record keyed by `job_id` + `input_hash`

Covered by `test_wp01_real_clinical_pipeline.py` and existing FV-01 lifecycle tests.

---

## 10. Segmentation evidence

| Scenario | Evidence |
|---|---|
| Real path receives uploaded path | Mocked `ToothInstanceNetEngine.segment` asserts `mesh_file_path == uploaded` |
| Fixture not called on real path | Fixture loader patched to assert if invoked |
| Real failure stays failure | `SEGMENTATION_FAILED`, `fixture=False`, 0 instances |
| Fixture blocked without allow | `MODEL_UNAVAILABLE` + blocked message |
| Hash-bound fixture accept/reject | Matching official STL accepted; unrelated STL rejected |

Live GPU inference on the uploaded official STLs was **not** completed in this environment (see §16).

---

## 11. Upper / lower evidence

- Arches processed separately with `ArchType.UPPER` / `ArchType.LOWER`
- Results stored under `segmentation_results.arches.upper|lower`
- Reconstruction preserves `arch` + `tooth_ref` (`upper:instance:N` / `lower:instance:N`)
- No cross-arch semantic collapse introduced
- P0.1 two-arch fixture regression retained behind TEST_FIXTURE allow flag

---

## 12. Provenance evidence

Persisted fields include:

- `processing_mode` (`real_case` | `test_fixture`)
- `case_id`, `job_id`, `input_hash`
- `source_mesh_path`, `source_mesh_sha256`
- `model_name`, `model_version`
- `fixture` / `provenance` flags (real path forces `fixture=False`)
- FDI never fabricated (`test_no_fdi_fabricated_in_reconstruction`)

---

## 13. Performance before/after (measured only)

| Measurement | Value | Notes |
|---|---|---|
| WP-01 focused pytest | **18 passed in 7.37s** (WP-01 + fixed regressions subset) | Includes hash-binding + real-path tests |
| Full backend pytest | **222 passed, 2 skipped in 180.40s** | Includes P0–P8 + WP-01 |
| Live TIN segmentation wall time on uploaded official STLs | **Not measured** | Blocked — no torch/CUDA in API `.venv` |
| Fixture reconstruction (P0.1 single test) | **1 passed in 4.92s** | Explicit TEST_FIXTURE path |

No invented FPS/ms claims for live inference.

---

## 14. Exact tests and results

| Suite | Result |
|---|---|
| `pytest tests/python/test_wp01_real_clinical_pipeline.py` (+ related fixes) | **18 passed** in focused re-run (7.37s) |
| `pytest tests/python` (full) | **222 passed, 2 skipped** in **180.40s** |
| `pnpm test` (apps/web) | **89 passed** (27 files) |
| `pnpm run typecheck` | **PASS** |
| `pnpm run lint` | **0 errors**, 1 pre-existing warning (`StageViewer` gizmoMode deps) |
| `pnpm run build` | **PASS** |

---

## 15. Remaining limitations

1. Live ToothInstanceNet inference still requires torch + CUDA + pointops + configured env — not packaged in the default API venv here.
2. Default backend remains configurable; operators must set `ALIGNERSTUDIO_SEGMENTATION_BACKEND=toothinstancenet` for real inference.
3. Treatment objectives after real segmentation remain engineering demo movements (not clinical prescriptions) — unchanged by design.
4. Clinical FDI still Not Available unless the model actually emits a number — never invented.
5. Occlusion / landmarks / anatomical axes remain out of WP-01 scope.

---

## 16. Blocker preventing real segmentation (this environment)

| Requirement | Status on this machine |
|---|---|
| Checkpoint `instseg_full.ckpt` | Present under `~/.cache/alignerstudio-research/...` |
| Source checkout @ verified revision | Present |
| `torch` in project `.venv` | **Missing** (`ModuleNotFoundError`) |
| NVIDIA driver / CUDA | **Unavailable** (`nvidia-smi` failed) |

Therefore WP-01 proves the **architecture and binding** with honest failure + mocked path assertions. A GPU-capable runtime is required before claiming measured live segmentation on uploaded STLs.

---

## 17. Explicit confirmation

**WP-02 Dental Intelligence 2.0 — NOT started.**  
**WP-03 World-Class 3D Workspace — NOT started.**

---

## Success criterion check

| Criterion | Met? |
|---|---|
| Real upload selects real geometry path | **Yes** (engine receives uploaded path) |
| Fixture cannot silently process production cases | **Yes** (blocked without allow; no fallback) |
| Provenance / job / hash binding | **Yes** |
| Failures stay failures | **Yes** |
| Live TIN end-to-end on GPU | **Blocked by environment** (documented) |
| World-class / doctor-ready claim | **Not claimed** |
