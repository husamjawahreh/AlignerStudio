# FV-02.2 — Scan preparation execution reliability

| | |
|---|---|
| Phase | FV-02.2 only |
| Date | 2026-09-26 |
| Verdict | **PASS** for the technical job path |
| Predecessor | [FV02_1_SCAN_PREPARATION.md](FV02_1_SCAN_PREPARATION.md) |

This is not clinical segmentation, clinical orientation, FDI, occlusion, or First Version readiness. Live ToothInstanceNet inference was not run. FV-03 was not started.

`READY_FOR_SEGMENTATION` remains a technical state. It means the acceptance gate passed for a later processing step. It does not mean the scan is clinically ready, numbered, oriented to a clinical frame, or in occlusion. `clinically_ready` stays false.

## Architecture

Orientation, trim, and cleanup — preview and apply — run on a process-local worker. The HTTP request queues the job and returns. There is one thread, named `alignerstudio-preparation`. There is no distributed queue and no new service.

Component removal, undo, reset, and accept stay on the request that calls them. Accept does not replay the mesh when a quality comparison is already stored.

A job record carries:

| Field | Meaning |
|---|---|
| `job_id`, `case_id`, `arch` | Identity. One active job per arch. |
| `source_artifact_hash` | SHA-256 of the immutable source at submit. |
| `operation`, `parameters`, `mode` | `orient`, `trim`, or `cleanup`; `preview` or `apply`. |
| `state` | `queued`, `running`, `completed`, `failed`, `cancelled`. |
| `queued_at`, `started_at`, `ended_at` | Timestamps. Duration is derived from start and end. |
| `progress`, `progress_stage` | Deterministic stages, not a guessed remaining time. |
| `output_artifact_hash` | Set only after a successful apply publishes a complete mesh. |
| `error` | `{code, message}` when the job fails or is cancelled. |
| `cache_hit`, `reused` | A hit still writes a provenance event that says the result was reused. |

Progress stages used by the worker: `load` (0.15, then 0.2 inside the operation), `operate` (0.5), `cache_lookup` (0.55), `recheck` (0.8), `commit` (0.92). A completed job is 1.0. A queued job is 0.

Error codes: `CANCELLED`, `STALE_JOB`, `PREPARATION_REFUSED`, `PREPARATION_FAILED`, `JOB_LOST`.

An equivalent submit (same case, arch, cache key, and mode) while a job is queued or running returns that job with `duplicate: true`. A different operation on the same arch returns HTTP 409. The request does not start a second worker.

If a persisted job is still `queued` or `running` and the live worker does not have it, a later read marks it `failed` with `JOB_LOST` and keeps a provenance event. The executor does not survive a process restart.

## Cache key

SHA-256 of canonical JSON:

- source SHA-256
- operation
- normalized parameters (booleans stay booleans, numbers rounded to 9 decimals, keys sorted)
- algorithm name
- algorithm version (`trimesh` version)
- replay prefix (the operations already committed)

Algorithms: `user_rigid_transform`, `vertex_pca_alignment`, `centroid_region_crop`, `trimesh_safe_cleanup`. Component removal stays synchronous and is not a cache key for this worker.

A different source hash cannot hit. The replay prefix is part of the key so the same trim is not reused after a different orientation. A preview-only entry has no output bytes, so a later apply of that key misses until an apply stores them. A hit writes provenance with `reused` true. It does not change truth state, FDI, occlusion, or clinical axes.

The cache is memory in this process. It is not a second clinical interpretation.

## Cancellation and stale results

A queued job cancels before it starts. A running job checks cancellation at each stage and again before the file is published. The worker writes `*.stl.partial`, checks the source hash, the output hash, the expected commit generation, and the cancel flag, then `replace`s the partial. On cancel, stale, or failure the partial is removed. A partial mesh is never the active prepared artifact.

`commit_generation` increments when an apply, undo, or reset commits. The job stores the generation it saw at submit. A mismatch fails as `STALE_JOB` and does not overwrite a newer prepared file. Accept and undo-accept do not bump the generation.

Cancelled and failed jobs stay on the preparation record. Their provenance is kept. The acceptance gate rejects an active prepared input that points at a failed or cancelled job.

## Artifact lineage

The source file is not rewritten. Each committed step appends lineage: source artifact id, source hash, operation chain (algorithm and version), output hash, and output path. The previous active entry becomes `superseded`. If that file is still named by history, undo, jobs, or another derived record, cleanup is `cleanup_deferred` with reason `referenced_by_preparation_history`. The file stays.

`retire_unreferenced_outputs` deletes only unpublished `*.stl.partial` files and prepared STLs whose path is not referenced. It does not use filesystem timestamps. `used_filesystem_timestamps` is false.

`privacy_log_view` still drops filenames, patient reference, and paths, including `output_path`.

## Acceptance gate

Before a prepared artifact is marked usable as a later segmentation input, the gate checks:

- the source file exists and its hash matches provenance
- the derived file exists and its hash matches the stored output, when operations exist
- the active lineage entry covers the operation chain
- coordinates are finite and face indices stay inside the vertex range
- stored face count matches the reloaded face count (STL reload does not share vertices, so the stored vertex count remains the in-memory count)
- readiness is one of `NOT_PREPARED`, `PREPARED`, `READY_FOR_SEGMENTATION`, `READY_WITH_WARNINGS`, `BLOCKED`
- no failed or cancelled job is the active prepared input

`technical_gate_passed` is the result of that check. `clinically_ready` is false in every case. `uses_derived_hash_as_source` stays false.

## Performance

One measurement on this host, 2026-09-26, of the same FV-02 file: 8,557,034 bytes, 513,417 vertices, 171,139 faces, SHA-256 `60aaafed87818b7cffd904056c4055748692bc280069af16325bff3b446e5a48`. The original file was only read. Work used a copy. Library: trimesh 5.1.0. manifold3d was not used. meshlib was not used. The report is `.research/tmp/fv02_2_report.json`.

| Step | Wall time | RSS after the step |
|---|---|---|
| 90° orientation preview, including prepared recheck | 2020.3 ms | 407.3 MB |
| Trim preview, box inset 2% of the bounds, including recheck | 1292.9 ms | 449.6 MB |
| Cleanup preview, including recheck | 1500.9 ms | 449.6 MB |
| Standalone source quality recheck | 1658.6 ms | 461.6 MB |
| Commit of the same 90° rotation | 4783.8 ms | 580.1 MB |
| Cache hit of that committed rotation | 149.3 ms | 563.9 MB |

`cache_hit` was true. Commit state was `completed`. Readiness stayed `PREPARED` because the open surface was not accepted. `clinical_axes`, `fdi_assigned`, and `clinically_ready` stayed false.

RSS before the steps was 267.6 MB, after trimesh was already imported. RSS after the cache hit was 563.9 MB. Peak RSS is `VmHWM` from `/proc/self/status`: 661.2 MB. That is the process high-water mark, not a filesystem timestamp, and it is not a delta from a cold process that started near 113 MB. FV-02.1 reported a peak near 768 MB from about 113 MB at process start. This run does not replace that baseline with a claim that peak memory fell by the difference.

Operation times include their own prepared recheck. The standalone recheck is an extra source load. Copies avoided: source quality reuses the stored intake inspection, and orient, trim, and cleanup mutate the working mesh. Copies retained: the prepared STL topology recheck still welds one copy, and publishing still allocates the STL buffer. Self-intersection stays `not_run`.

## Browser verification

Live, not skipped. Playwright `tests/e2e/fv02_2.preparation.spec.ts` passed in 33.4 s against `http://127.0.0.1:5177` and `http://127.0.0.1:8000`.

The test created a case, uploaded the real 8,557,034-byte STL, waited until intake reported Valid, opened File details, submitted Rotate 90° Z, observed the upper preparation job reach `completed`, and asserted preparation status `PREPARED` on the form and in the inspector. The status text did not say the arch was clinically segmented. The rotate control was enabled again after the job finished. No screenshot suite was added.

Environment notes from this host:

- The user's Vite process was on port 5177. The spec's default web URL is 5173, so the run set `P8_WEB_URL`.
- A process already bound to 5173 served an older frontend. It accepted the STL upload and did not produce intake quality, so it was not used for this result.
- The API allow-list includes localhost and 127.0.0.1 on ports 5173–5177 so a Vite fallback port can call the API. Before the API process was restarted, `OPTIONS /cases` from 5177 returned 400.
- An earlier attempt hit Create Case while a previous mesh job still held the interpreter, and the case id was not visible within 5 s. The wait is 30 s. The run reported above passed after that change.

## Tests

`tests/python/test_fv02_2_preparation_jobs.py` covers job lifecycle, cancellation, stale rejection, cache hit and miss, provenance, lineage, the acceptance gate, failed and cancelled input rejection, cleanup safety, and this real-scan measurement.

Frontend: `CaseIntakePanel.test.tsx` renders operation, state, progress, elapsed time, source and derived relationship, and blocks a second submit while the job is active. `wave10AdaptiveInspector.test.tsx` shows the job text in the case inspector and does not add preparation buttons there.

## Limitations still open

- Clinical orientation, landmarks, and FDI are not produced.
- Dual arches do not establish occlusion. The older plan route still asks for both arches.
- Trim does not choose a clinically important boundary.
- Cleanup does not close holes or repair an open crown.
- Self-intersection is `not_run`.
- STL component ids still depend on a welded copy. The source bytes stay unwelded.
- The prepared topology recheck still welds one copy. The standalone recheck on this file was 1658.6 ms.
- The worker and the cache are process-local. A restart does not continue a running job.
- Component removal, undo, reset, and accept are not background jobs.
- `READY_FOR_SEGMENTATION` is not clinical readiness.
