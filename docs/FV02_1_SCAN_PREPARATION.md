# FV-02.1 — Scan preparation foundation

| | |
|---|---|
| Phase | FV-02.1 only |
| Date | 2026-09-26 |
| Verdict | **PASS** |
| Predecessor | [FV02_CLINICAL_DATA_INTAKE.md](FV02_CLINICAL_DATA_INTAKE.md) |

This is not clinical segmentation, clinical orientation, or First Version readiness. Live ToothInstanceNet inference is unchanged and was not run.

## Pipeline

```
SOURCE_ARTIFACT
    → PREPARATION_OPERATION
    → DERIVED_PREPARED_ARTIFACT
    → FUTURE_SEGMENTATION_INPUT
```

The source file is never rewritten. Every prepared file stores `source_artifact_id`, `source_sha256`, `output_sha256`, the operation, algorithm, trimesh version, parameters, timestamp, truth state, and limitations. `uses_derived_hash_as_source` stays false. A prepared mesh is `DERIVED_GEOMETRY`, not observed anatomy.

Replaying the source plus the stored parameters reproduces the prepared SHA-256. A new operation writes a new version file. Undo and reset rebuild from the source. Older derived files are left on disk and are no longer the active mesh.

## Operations

| Operation | What it does | Truth |
|---|---|---|
| User rotate / translate | Rigid transform from degrees and a translation. Reset clears the chain. | `USER_PROVIDED` |
| Geometric PCA | Aligns principal axes and moves the centroid to the origin when the user applies it. | `COMPUTED_GEOMETRIC_ORIENTATION`, `clinical_axes` false |
| Standard views and fit | Existing viewport commands. They do not write a mesh. | Not a preparation transform |
| Trim | User axis-aligned box or plane. Faces are kept or dropped by centroid. No cap is added. Preview writes nothing. | `USER_PROVIDED` |
| Cleanup | Merge duplicate vertices, drop degenerate faces, drop exact duplicate faces, drop components that are degenerate or non-finite. | `DERIVED` |
| Components | List, or remove ids the user selects. STL ids are computed on a welded copy because STL does not share indices. | `USER_PROVIDED` |

Hole filling, watertight conversion, gingival closing, and anatomy reconstruction are refused. There is no automatic cut. An empty region is refused before a file is written.

## Readiness

| State | Meaning |
|---|---|
| `NOT_PREPARED` | No committed geometry step, and the user has not accepted the source. |
| `PREPARED` | At least one step was rechecked. It has not been accepted for a later processing step. |
| `READY_FOR_SEGMENTATION` | The user accepted a mesh with no quality blockers and no warnings. |
| `READY_WITH_WARNINGS` | The user accepted a mesh that is open or otherwise warned, and not blocked. |
| `BLOCKED` | Recheck found a blocker, such as an empty or non-finite result. |

Acceptance does not mean the scan is clinically segmented, clinically oriented, numbered, or in occlusion. An open crown can be `READY_WITH_WARNINGS`. It is not rejected for being non-watertight.

Upper only, lower only, and both arches each keep their own history and source hash. Two prepared arches do not create a bite registration.

## Quality recheck

After every committed step the intake checks run again: vertex and face counts, boundaries, non-manifold edges, degenerates, duplicate faces, components, bounding box, watertightness, and warnings. Source and prepared summaries are stored together. Self-intersection stays `not_run`.

## Technology

trimesh 5.1.0 performs the operations. manifold3d is installed and unused. meshlib is declared and not importable in this environment. Open3D was not added. No new geometry library was added.

## Performance

The same local binary STL measured in FV-02: 8,557,034 bytes, 513,417 vertices, 171,139 faces, SHA-256 `60aaafed87818b7cffd904056c4055748692bc280069af16325bff3b446e5a48`. The original file was only read. Preparation ran on a copy.

| Step | Time |
|---|---|
| 90° orientation preview, including quality recheck | 4.94 s |
| Trim preview of a box inset by 2% of the bounds, including recheck | 2.78 s |
| Cleanup preview (merge, degenerate, duplicate faces), including recheck | 2.51 s |
| Persist that 90° rotation | 2.65 s |

Peak RSS during the measurement was about 768 MB, from about 113 MB at process start. The prepared result was `PREPARED` because the open surface was not accepted. `clinical_axes` and `fdi_assigned` stayed false.

These steps do not run when a case opens. This measurement used the request thread. FV-02.2 moved orientation, trim, and cleanup onto a local job. The cost here is the weld used to recheck STL topology. Self-intersection repair is not included.

## Privacy

Preparation records live on the existing case JSON. `privacy_log_view` drops filenames, patient reference, source paths, and output paths, including paths nested under the preparation. The screen still shows the filename the user imported. Nothing is sent to a cloud service.

## Tests

`tests/python/test_fv02_1_scan_preparation.py`: 7 tests. With the FV-02 intake tests: 18 passed.

Frontend DOM tests: `CaseIntakePanel.test.tsx` covers the preparation form, `wave10AdaptiveInspector.test.tsx` covers a status row with no preparation buttons, and `caseIntake.test.ts` covers the readiness wording. The related frontend run was 37 passed. A live browser upload was not exercised.

## Limitations

- Clinical orientation, landmarks, and FDI are not produced.
- Dual arches do not establish occlusion. The older plan route still asks for both arches.
- Trim does not choose a clinically important boundary.
- Cleanup does not repair an open crown.
- Quality recheck on this scan is several seconds and holds a large in-memory copy.
- Undo and reset do not delete earlier derived files. FV-02.2 marks referenced history `cleanup_deferred` and deletes only unreferenced outputs.
- STL component ids depend on a welded copy. The source bytes stay unwelded.

Job execution, cache reuse, cancellation, and the technical acceptance gate are recorded in [FV02_2_SCAN_PREPARATION.md](FV02_2_SCAN_PREPARATION.md). The timings in this file are the FV-02.1 request-thread measurement. They are not the FV-02.2 job-path measurement.
