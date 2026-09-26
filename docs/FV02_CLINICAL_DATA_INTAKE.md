# FV-02 — Clinical data intake and scan preparation

| | |
|---|---|
| Phase | FV-02 only |
| Date | 2026-09-26 |
| Verdict | **PASS** |
| Clinical segmentation | Not claimed |
| First Version | Not claimed |

## Formats

| Format | Support | What the bytes do not contain |
|---|---|---|
| STL binary | Yes. Triangle count is taken from the 84-byte header when the file length matches. | Patient identity, FDI, arch, guaranteed units. |
| STL ASCII | Yes. `solid` / `facet` text. | Same absences as binary STL. Face normals are read only when a `facet normal` is non-zero. |
| PLY | Yes, ASCII and other PLY trimesh can load. | Units are not inferred. Color is true only when the loader marks visual data as defined. |
| OBJ | Yes. A scene with several geometries keeps every mesh object's name and counts. Inspection may concatenate those meshes in memory. Nothing is dropped and nothing is written back. | Object names are not gingiva, bite, or tooth numbers. |

## Source artifact

`inspect_source_file` hashes the file, loads it, hashes it again, and does not write it. The stored record includes case id, artifact id, original filename, format, SHA-256, byte size, import time, local storage path, vertex and face counts, bounding box, surface area, volume only when the welded topology is watertight, normals, color availability, `units: null`, coordinate metadata, warnings, blockers, readiness, `truth_state=COMPUTED`, and `provenance=real`.

Uploaded bytes are saved under a generated file name. The original filename is kept on the case record for the intake screen.

## Quality

Blockers (`BLOCKED_INVALID_INPUT`): missing file, unreadable file, empty mesh, zero vertices, zero faces, non-finite coordinates.

Warnings (`READY_WITH_WARNINGS`): duplicate vertex positions on indexed formats, degenerate faces, duplicate faces, boundary edges, non-manifold edges, more than one component, an open surface, a suspicious extent (above 500 or below 0.01 in file coordinates).

An open crown is a warning. It is not rejected for being non-watertight.

STL connectivity is measured on a welded copy. That copy is not saved. The source hash does not change. Self-intersection is `not_run` during import because it is too expensive to put on case open.

A closed box is `READY`. The legacy `validate_mesh_file` route still applies a 1000-triangle sanity check for the older validate button. That check is not the FV-02 readiness value.

## Repair

Not automatic. `POST /cases/{id}/uploads/{arch}/derive-clean` writes a new file with trimesh vertex merge and degenerate-face removal. The record stores the source hash, output hash, algorithm, trimesh version, parameters, `truth_state=DERIVED`, and a limitation that the result is not a clinical tooth and was not made watertight. Segmentation input keeps the source hash.

| Library | This environment | Intake use |
|---|---|---|
| trimesh 5.1.0 | importable | Parse, quality, explicit derived cleanup. A tiny merge took 0.28 ms. |
| manifold3d | importable, version attribute absent | Not used. No watertight conversion of scans. |
| meshlib | Declared in `services/api/pyproject.toml`, not importable in this virtualenv | Not installed for this phase. |
| Open3D | not added | No measured intake gap required it. |

## Orientation

| Kind | Meaning |
|---|---|
| `SOURCE_COORDINATES` | The file's own numbers. Not rewritten. |
| `NORMALIZED_VIEW_COORDINATES` | A centroid translation stored for a later view. `applied_to_source` is false. |
| `COMPUTED_GEOMETRIC_ORIENTATION` | Vertex PCA. `clinical_axes` is false. |
| `CLINICAL_ORIENTATION` | Unavailable. |
| `MODEL_ORIENTATION` | Unavailable. |

## Arch

`upper` or `lower` is stored only when the upload parameter says so, with `truth=USER_PROVIDED` and no confidence score. Otherwise the value is `ARCH_UNKNOWN`. A filename is never parsed. Upper only, lower only, and both are valid. `occlusion_established`, bite, contact, and jaw relationship stay false. `fdi_assigned` stays false.

## Privacy

Retained in the local case JSON: technical case id, source SHA-256, mesh statistics, the filename the user chose, and `patient_reference` if they typed one.

Not put in `privacy_log_view`: original filename, patient reference, source path.

The application does not upload the case to a cloud service. A scan hash is still personal data. This is not a de-identification product.

## Performance

One local binary STL already on disk, 8,557,034 bytes, 513,417 vertices, 171,139 faces:

| Step | Time |
|---|---|
| Hash | 36 ms |
| Parse | 11 ms |
| Inspection, including the STL weld | 910 ms |
| Total | 1.01 s |
| Repair | not run |
| Readiness | `READY_WITH_WARNINGS` (`boundary_edges`, `disconnected_components`, `open_surface`) |

No repair and no self-intersection ran. The source length was unchanged.

## Persistence

Intake artifacts live on the existing case record in the same JSON store. Reopen returns the same source hash. There is no second case store.

## Tests

`tests/python/test_fv02_clinical_intake.py`: 11 tests, included in 17 passed with mesh-validation and case-domain tests.

Frontend: `CaseIntakePanel.test.tsx`, `App.test.tsx`, and `caseIntake.test.ts`: 11 passed.

## Limitations

- Self-intersection is not part of import.
- meshlib is not installed in this environment.
- The plan endpoint still requires both arches even though intake does not.
- Clinical orientation is intentionally absent until a later phase supplies landmarks or a doctor transform.
- The measured dense mesh is one local STL, not a new multi-scanner corpus.
