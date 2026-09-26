# Aligner Studio — Capability Matrix

| | |
|---|---|
| Document ID | `AS-FV-MATRIX-1.7` |
| Status | Authoritative capability inventory |
| Audit date | 2026-09-26 |
| Companion | [ALIGNER_STUDIO_WORLD_CLASS_FIRST_VERSION_MASTER_PLAN.md](ALIGNER_STUDIO_WORLD_CLASS_FIRST_VERSION_MASTER_PLAN.md) |

`IMPLEMENTED_AND_VERIFIED` means automated tests lock an engineering behavior. It does not mean First Version acceptance or clinical approval. No row has passed the final gate in the master plan.

Field order on every row: **Status · Existing · Evidence · Missing · Dependencies · Data · Technology · Acceptance · Performance · Real-case · Clinical limit · Provenance**.

Shared technology notes: Three.js and three-mesh-bvh stay the viewport until measured otherwise. trimesh, manifold3d, and meshlib stay behind the production-geometry adapter. ToothInstanceNet is the segmentation path to prove. Other models stay challengers. License flags are in the master plan section 10.

---

## A. Clinical data and case intake

### A1. STL import
`IMPLEMENTED_AND_VERIFIED` · Binary and ASCII STL are inspected without rewriting the file. STL does not supply units, FDI, or arch. · `tests/python/test_fv02_clinical_intake.py`, `docs/FV02_CLINICAL_DATA_INTAKE.md`. · None for reading STL. The legacy 1000-triangle validate route is a separate gate. · A1. · Scanner STL. · trimesh 5.1.0. · Source SHA-256 matches the stored bytes after inspection. · An 8.2 MB binary STL: hash 36 ms, parse 11 ms, inspection 910 ms. · Required. One local STL measured. · File acceptance is not a diagnosis. · Source SHA-256. The storage name is a generated id, not the original filename.

### A2. PLY import
`IMPLEMENTED_AND_VERIFIED` · `.ply` uploads use the same immutable source contract as STL. Color is recorded only when the loader marks visual data as defined. Units are not invented. · `tests/python/test_fv02_clinical_intake.py`. · A scanner PLY with a real color channel still needs a measured sample. · A1. · PLY exports. · trimesh. · A PLY box round-trips with a source hash and `units_encoded` false. · Included in the format test, not the 8.2 MB STL sample. · Required for intake. · Color is not a clinical label. · Same source hash chain as A1.

### A3. OBJ import
`IMPLEMENTED_AND_VERIFIED` · `.obj` is accepted. Multiple geometries are listed and not dropped. They are concatenated only in memory for inspection. · `tests/python/test_fv02_clinical_intake.py`, `tests/fixtures/synthetic_segmentation_arch.obj` (engineering fixture, labeled in the file). · A production scanner OBJ is not in this measurement. · A1. · OBJ exports. · trimesh. · Object names and counts are kept. `fdi_assigned` stays false. · Fixture OBJ only. · Supported. · Multi-object text is not occlusion or gingiva classification. · Source hash plus per-object counts.

### A4. Upper/lower identification
`IMPLEMENTED_BUT_PARTIAL` · Arch is stored only from the explicit upload parameter as `USER_PROVIDED`. Missing means `ARCH_UNKNOWN`. Filename is not used. One arch is a valid intake. Dual presence does not set occlusion. The older plan route still asks for both arches before a plan. · `tests/python/test_fv02_clinical_intake.py`. · No computed arch suggestion. · A1. · The user's arch choice. · None. · A file named like an arch stays `ARCH_UNKNOWN` unless the parameter is set. · Not a hot path. · Required. · There is no inferred clinical arch. · `arch.truth` on the artifact.

### A5. Scan orientation
`IMPLEMENTED_BUT_PARTIAL` · Source coordinates stay on the file. A user rotation or translation is a derived preparation with truth `USER_PROVIDED`. PCA, when the user applies it, is `COMPUTED_GEOMETRIC_ORIENTATION` with `clinical_axes` false. Preview and commit of that transform run on a process-local job. Standard views and fit stay camera commands and do not write a mesh. Clinical and model orientation stay unavailable. · `tests/python/test_fv02_1_scan_preparation.py`, `tests/python/test_fv02_2_preparation_jobs.py`, `docs/FV02_2_SCAN_PREPARATION.md`. · A validated clinical frame. · A1. · Scan in scanner coordinates. · trimesh 5.1.0 and NumPy. · The source hash is unchanged after a persisted transform, and replaying the parameters reproduces the prepared hash. A cache hit records reuse and does not cross a different source hash. · On the 8,557,034-byte STL, a 90° job-path preview was 2020.3 ms including the prepared recheck. Commit of that rotation was 4783.8 ms. A cache hit was 149.3 ms. Peak RSS (`VmHWM`) was 661.2 MB from 267.6 MB after trimesh was already imported. It does not run on import. · Required. · PCA is not a clinical axis. `READY_FOR_SEGMENTATION` is not clinical readiness. · Transform matrix, source hash, job id, and truth state on the preparation version.

### A6. Mesh quality
`IMPLEMENTED_BUT_PARTIAL` · Intake reports empty, non-finite, degenerate, duplicate, non-manifold, boundary, components, scale, and watertightness. The same checks run again after each preparation step, and the source counts are kept beside the prepared counts. Open surfaces are warnings. Self-intersection is `not_run`. STL topology is measured on a welded copy that is not saved. A technical gate must pass before the prepared mesh is marked as a later segmentation input. · `tests/python/test_fv02_clinical_intake.py`, `tests/python/test_fv02_1_scan_preparation.py`, `tests/python/test_fv02_2_preparation_jobs.py`. · Self-intersection on the hot path, only if a later measurement says it is cheap enough. · A1. · The uploaded mesh. · trimesh. manifold3d is present and unused. meshlib is declared and not importable here. · `BLOCKED_INVALID_INPUT` only for unreadable, empty, or non-finite input. An open crown can still be `READY_WITH_WARNINGS`. Failed and cancelled jobs cannot be the active prepared input. · Import inspection of 171,139 faces was about 0.91 s. On the FV-02.2 job-path measurement, a standalone source quality recheck was 1658.6 ms. Orientation, trim, and cleanup times include their own prepared recheck. · Required. The measured STL is an open surface and was not blocked. · QC is `COMPUTED`, not a diagnosis. `clinically_ready` stays false. · Check names and readiness on the artifact and on the preparation comparison.

### A7. Duplicate and invalid data
`IMPLEMENTED_BUT_PARTIAL` · Input hash identities jobs. Fixture loader rejects a hash mismatch. Empty and tiny meshes fail. · `test_wp01_real_clinical_pipeline.py`, `test_fv01_processing_lifecycle.py`, `test_toothinstancenet_fixture.py`. · Doctor-visible duplicate-upload policy and corrupt-file recovery that keeps the previous good asset. · A1, A6. · Bytes of the upload. · Existing hash helpers. · A second upload of different bytes cannot reuse the old segmentation. · Hash is cheap. · Required. · Duplicate detection is not a statement that two patients match. · Input hash on the job and the segmentation record.

### A8. Missing data
`IMPLEMENTED_BUT_PARTIAL` · Missing arch, missing segmentation, and missing registration become blocked or `NOT_AVAILABLE` states in workflow and occlusion contracts. · `workflowWave7.test.ts`, `test_wp08_occlusion_advanced_anatomy.py`. · A single checklist of missing inputs for the active step, including bite and CBCT when those steps are entered. · Workflow resolver. · Whatever the case actually lacks. · Existing truth labels. · The doctor can continue on available arches and cannot enter a step that needs absent data without an explicit limitation. · Not a hot path. · Required. · Absence is `NOT_AVAILABLE`, not a clinical finding of "no treatment needed." · Reason string on the blocked step.

### A9. Ambiguous identity
`IMPLEMENTED_BUT_PARTIAL` · ToothInstanceNet mapping reports duplicate and missing class numbers and does not repair them. Planning can run semantic-only on `tooth_ref`. · `engines/segmentation/toothinstancenet.py`, `test_semantic_only_planning.py`, `test_fv01_provenance_guards.py`. · A review UI that lets a doctor resolve or explicitly leave identity unresolved. · B2, B5. · Segmented instances. · Doctor correction before any numbering model. · Unresolved teeth stay plannable by `tooth_ref` and cannot receive a fabricated FDI. · Not a hot path. · Required. The official artifact has repeated class labels. · Seven-class numbers are not unique identity. · `tooth_ref` plus identification status.

### A10. Real gingiva when observed
`NOT_AVAILABLE_BY_DATA` · No gingiva segmentation. The viewer can draw synthetic gingiva. · `apps/web/src/viewer/syntheticGingiva.test.ts`, `test_fv01_provenance_guards.py`. · Detect and label observed gingival surface when a scan contains it. Keep synthetic drawing on a separate layer. · B1. · A scan where gingiva is actually present and segmented. · Segmentation model or doctor paint. · Observed gingiva is a mesh with class `SEGMENTED` or `OBSERVED`. Synthetic gum never shares that id. · Display-only synthetic path must stay cheap. · Required before gingiva is called real. · Crown-only STLs do not prove gingiva. · Separate object id from teeth.

### A11. Scan cleanup
`IMPLEMENTED_BUT_PARTIAL` · Explicit cleanup can merge duplicate vertices, drop degenerate faces, drop exact duplicate faces, and drop components that are degenerate or non-finite. A user box or plane trim and a selected-component removal are separate derived steps. Cleanup and trim preview and commit run on the same local job as orientation. None of these run on import, fill holes, or force a watertight crown. Source bytes stay put. Undo and reset rebuild from the source. Referenced superseded files stay and are marked `cleanup_deferred`. · `tests/python/test_fv02_1_scan_preparation.py`, `tests/python/test_fv02_2_preparation_jobs.py`, `docs/FV02_2_SCAN_PREPARATION.md`. · Automatic base removal, hole closing, and anatomy reconstruction. · A6. · Raw scan. · trimesh 5.1.0. manifold3d was not used. meshlib is not importable here. Open3D was not added. · The prepared hash is reproducible from the source plus parameters, and `uses_derived_hash_as_source` stays false. · Cleanup preview on the 8,557,034-byte STL, on the FV-02.2 job path, was 1500.9 ms including the quality recheck. Trim preview on the same run was 1292.9 ms. · Optional. · A derived mesh is `DERIVED_GEOMETRY`, not observed anatomy. · Algorithm, library version, parameters, source hash, output hash, and lineage lifecycle.

### A12. Case metadata
`IMPLEMENTED_BUT_PARTIAL` · Case id, status, arch assets, optional `patient_reference` string. · `domain/case/models.py`, `test_case_domain.py`. · Structured clinician, dates, notes, and scanner model without turning notes into clinical facts. · A1. · User entry. · Existing case store. · Metadata round-trips across restart. · Not a hot path. · Required for a real practice workflow. · Free text is not a diagnosis. · Field-level source: user-entered.

### A13. Persistence
`IMPLEMENTED_AND_VERIFIED` · `cases.json`, upload files, segmentation store, gzip-pickle treatment sessions. · `test_wp13_reliability.py`, `test_p7_performance_reliability.py`, `test_api_cases.py`. · Versioned schema instead of pickle; documented backup location. · A1. · Local disk. · Current store. Keep until FV-13 replaces pickle. · Restart returns the same case hash and segmentation binding. · Session compose cold was 104.7 s on the official upper path. That is a planning-session cost, not the JSON case write. · Required. · Local files are not an anonymized archive. · Paths and schema version.

### A14. Anonymization and privacy
`IMPLEMENTED_BUT_PARTIAL` · The case JSON keeps the technical case id, the source hash, and the user-entered patient reference and filename because the intake screen shows them. `privacy_log_view` drops filename, patient reference, and source path. Uploaded bytes are stored under a generated file name. No cloud service was added. · `tests/python/test_fv02_clinical_intake.py`, `docs/FV02_CLINICAL_DATA_INTAKE.md`. · Export stripping and a clinic privacy policy. · A12. · Whatever the user types. · Local JSON store. · A log view of a file named with a person does not contain that name. · Not a hot path. · Required before a clinic install. · A hash of a scan is still personal data. · Field list in the FV-02 document.

---

## B. Segmentation and dental anatomy

### B1. Real segmentation
`IMPLEMENTED_BUT_NOT_PROVEN` + `ENVIRONMENT_BLOCKED` · Real uploads call ToothInstanceNet only when the runtime probe says the backend is executable. FV-03 refuses raw, stale, partial, and failed preparation inputs and persists the prepared SHA. FV-01.1 read the pinned checkpoint: DentalNet, 6 input channels, offsets/sigmas, one seed logit, 7 identify logits, instance ids from clustering. FV-03.1 self-test on this host is `ENVIRONMENT_UNAVAILABLE` with blockers `DRIVER_UNAVAILABLE`, `PYTORCH_UNAVAILABLE`, and `CUDA_EXTENSION_UNAVAILABLE`. Checkpoint metadata is `TENSOR_CONTRACT_ESTABLISHED` and is not readiness. No inference ran. CPU fallback was ruled out. A blocked run stores the blocker, seals an evidence bundle, and does not fabricate instances. · `tests/python/test_fv03_segmentation.py`, `tests/python/test_fv03_1_runtime.py`, `docs/FV03_SEGMENTATION.md`, `docs/FV03_1_SEGMENTATION_RUNTIME.md`, `.research/tmp/fv03_report.json`, `.research/tmp/fv03_1_report.json`. · A clean CUDA machine must execute the same accepted prepared artifact. A second real case is still required. · A1, A5, PyTorch CUDA, pointops, teethland source revision `424252e3d94a1565c8c2090eb5bb456b76386b93`. · An accepted prepared arch. · ToothInstanceNet behind the FV-03 backend interface. PyTorch is not an application startup dependency. Not production-ready on this host. · `READY_FOR_INFERENCE`, then a candidate whose prepared SHA, model SHA, and `clinical_accuracy_claim` false are stored, with no fabricated FDI. · FV-03 record: prepared load 145.5 ms, input gate 326.3 ms, capability detection 1511.3 ms, inference not attempted, peak RSS 529.3 MB. FV-03.1 appended a later probe: load 34.1 ms, gate 80.2 ms, capability 340.6 ms, inference not entered, peak RSS 421.0 MB. The later peak does not replace 529.3 MB. · Required. Not met. · Not clinical accuracy. Not FDI. Seven classes are `NOT_ESTABLISHED`. · Pinned SHA-256 `100c68a9b120402cc75539eff6347bd998bce8b1d4f01550638f471797d70803`.

### B2. Tooth instance identity
`IMPLEMENTED_BUT_PARTIAL` · A candidate uses an internal instance id, not FDI. The model class is stored raw and mapped as `NOT_ESTABLISHED`. Official artifact still has 14 instances per arch under the older `tooth_ref` path. · `tests/python/test_fv03_segmentation.py`, manifest `unique_instances` 0–13 per arch. · Identity that survives a live model run and a doctor merge/split on that run. · B1. · Segmentation output. · FV-03 candidate contract. · Same prepared SHA and parameters produce the same candidate ids when a backend executes. · Not measured on a live forward pass. · Required. · Instance id is not a tooth number. · Instance id, raw model class, prepared SHA, run id.

### B3. Authoritative tooth numbering
`NOT_AVAILABLE_BY_DATA` · The identify head has 7 outputs. That count is a weight shape, not a stored class-name table. FV-03 keeps the raw class and sets the mapping to `NOT_ESTABLISHED`. `config.yaml` in the pinned checkout does not match the only datamodule setting that returns 7. The live mapper still does not write FDI. · `tests/python/test_fv03_segmentation.py`, `test_fv01_1_execution.py`. · Doctor-assigned or measured numbering. · B2, B5. · A method that distinguishes left from right. This checkpoint does not encode one. · Doctor assignment before a model. · No FDI is stored unless `fdi_authoritative` is true. · Not a hot path. · Required before any FDI rule. · Seven logits are not FDI. Left/right in the yaml is unverified. · Raw model class plus `fdi: null`.

### B4. Manual correction
`IMPLEMENTED_BUT_PARTIAL` · Accept, reject, hide, show, mark for review, merge, undo, redo, and reset write provenance on a candidate: previous state hash, affected instance ids, operation, parameters, timestamp, and a geometry hash when faces change. The model snapshot is not rewritten. Accept does not set `VERIFIED`. Split is `SPLIT_UNAVAILABLE` because the form has no safe face partition. Manual segmentation correction is `NOT_IMPLEMENTED` and does not replace the model. These edits were tested with a deterministic mock because this host produced no instances. There is no brush. · `tests/python/test_fv03_segmentation.py`, `tests/python/test_fv03_1_runtime.py`, `docs/FV03_1_SEGMENTATION_RUNTIME.md`. · Brush or boundary paint, and the same edits on a live ToothInstanceNet candidate. · B1. · Candidate face indices. · FV-03.1 review record. · A merge of overlapping faces is refused, and undo restores the recorded operation without changing the model snapshot. · Not timed on a real segmentation. · Required. · A doctor edit is not clinical verification and does not assign FDI. · Review operation, parent instance ids, prepared SHA, geometry hash.

### B5. Segmentation review
`IMPLEMENTED_BUT_PARTIAL` · The intake form shows model-derived segmentation, `NOT_ESTABLISHED` identity, `QUALITY_EVALUATION NOT_AVAILABLE`, and either `ENVIRONMENT_BLOCKED` or `SEGMENTATION_COMPLETED`. Review controls render only when a completed result has `real_inference` true. The inspector shows status and does not start a job. The older analysis step still shows pipeline truth. · `SegmentationReviewForm.test.tsx`, `wave10AdaptiveInspector.test.tsx`, `tests/e2e/fv03_segmentation.spec.ts`, `docs/FV03_1_SEGMENTATION_RUNTIME.md`. · Review of a live candidate on two real cases. · B1, B4. · Segmentation candidate or an explicit blocker. · Existing inspector plus the FV-03 form. · A blocked run does not say the case is segmented or clinically verified. · Not separately timed beyond the capability probe. · Required on both real cases. · Review UI must not present a model class as FDI. · Run id, capability state, semantic identity, self-test state.

### B6. Tooth boundaries
`IMPLEMENTED_BUT_PARTIAL` · Instance meshes are the boundary. No boundary-edit or margin curve. · Fixture reconstruction tests. · Doctor-visible boundary and a way to fix leakage between neighbors. · B4. · Instance faces. · Mesh adjacency from the segmentation. · Boundary edits change only the recorded faces. · Boundary display must use the BVH path, not a second full copy, once measured. · Required. · Boundary is `SEGMENTED`. · Face index set and parent mesh hash.

### B7. Crown geometry
`IMPLEMENTED_BUT_PARTIAL` · Crown-only STL is the default extent (`domain/tooth/anatomy_extent.py`). · `test_p3_anatomical_intelligence.py`, `test_wp08_occlusion_advanced_anatomy.py`. · Keep crown meshes as the planning surface. Do not invent roots to complete a crown. · B1. · Segmented crowns. · trimesh. · Crown mesh hash matches the segmentation child. · Official tooth probe: 2,957 verts / 5,728 faces, not watertight. · Required. · Crown surface is not the whole tooth. · `CROWN_ONLY` extent flag.

### B8. Roots when real evidence exists
`NOT_AVAILABLE_BY_DATA` + `REQUIRES_REAL_DATA` · `engines/validation/root_bone.py` raises if the source is crown STL and the requested pathway is CBCT. · `test_wp08_occlusion_advanced_anatomy.py`. · A CBCT segmentation path (FV-09) and a reviewed root mesh. · I12, I13. · DICOM/CBCT plus a registration to the crown. · Slicer dental segmentators are candidates, not integrations. · With no volume, roots stay `NOT_AVAILABLE`. With a reviewed volume, roots are `SEGMENTED` or `RECONSTRUCTED` as the method warrants. · Unmeasured. · A CBCT case, separate from the two STL acceptance cases. · Crown STLs never grow roots. · Volume hash, segmentor version, registration id.

### B9. Landmarks
`IMPLEMENTED_BUT_NOT_WORLD_CLASS` · `landmarks_for_instance()` uses extrema along the computed frame, not anatomical points. A landmark checkpoint exists in research inventory and was not used for the official artifact. · `test_p3_anatomical_intelligence.py`, `test_wp02_dental_intelligence.py`. · Anatomical landmarks from a measured model or doctor placement. · B7, FV-03. · Crown mesh today. · Current extrema algorithm stays labeled `COMPUTED`. ToothInstanceNet landmarks only after a real-case trial. · Extrema cannot be displayed as cusp tips or CEJ. · Cheap relative to validation. · Required before landmark-based registration. · Extrema are `COMPUTED`. Anatomical landmarks are `PROPOSED` until reviewed. · Algorithm id on each point.

### B10. Local clinical axes
`NOT_AVAILABLE_BY_DATA` · PCA axes exist and are labeled computed. Staging readiness marks clinical axes unavailable. · `test_wp02_dental_intelligence.py`, `domain/treatment_plan/smart_staging.py`. · A defined clinical-axis method or doctor adjustment. · B9 or an explicit frame definition. · More than a crown point cloud if the method needs it. · Do not rename PCA to clinical. · UI says computed frame or unavailable. · Frame build is part of intelligence, previously measured inside WP-02 tests as deterministic, not as a budget. · Required before axis-constrained movement is called clinical. · PCA is `COMPUTED`. · Frame algorithm version.

### B11. Dental coordinate systems
`IMPLEMENTED_BUT_PARTIAL` · Tooth-local frames from arrangement geometry; world gizmo is separate. · `test_arrangement_phase4.py`, `test_treatment_planning_phase5.py`. · One documented frame chain: scan, arch, tooth, stage. · B10, A5. · Segmented crowns. · Existing frame code. · A movement stored in one frame reproduces in another within a stated numeric tolerance. · Not separately budgeted. · Required. · Frame axes are not occlusal planes unless orientation was reviewed. · Frame ids on each transform.

### B12. Arch membership
`IMPLEMENTED_AND_VERIFIED` · Each instance is bound to the uploaded arch. · `test_p0_1_two_arch_presentation.py`, arrangement tests. · Cross-arch mistakes are a data error to surface, not a silent relabel. · A4, B2. · Arch assignment plus instances. · Existing models. · A tooth cannot appear on both arches. · Not a hot path. · Required. · Membership follows the upload, not an inferred jaw from shape alone. · Arch id on `tooth_ref`.

### B13. Arch form
`IMPLEMENTED_BUT_PARTIAL` · Descriptive measurements in `engines/arrangement/arch_analysis.py`. No editable curve. · `test_arrangement_phase4.py`, `docs` are not the evidence; the tests are. · Editable arch curve used by setup (FV-05). · B12. · Tooth centroids or a doctor curve. · Current analysis. A fit curve is new work. · Changing the curve versions the setup. · Unmeasured. · Required. · A fitted curve is `COMPUTED` or `PLANNED`, not anatomy. · Curve parameters and input tooth set.

### B14. Tooth arrangement
`IMPLEMENTED_BUT_PARTIAL` · Ordering and descriptive relations from identified teeth. · `test_arrangement_phase4.py`. · Arrangement that stays correct when numbering is unresolved, using `tooth_ref` order along the arch. · B12, B13. · Positions of instances. · Existing arrangement engine. · Order is stable for a fixed segmentation. · Not a hot path. · Required. · Order is `COMPUTED`. · Algorithm version.

### B15. Missing-tooth state without false absence
`IMPLEMENTED_AND_VERIFIED` · A missing-teeth flag can be set from unidentified data. The official path does not invent absent FDI numbers to fill 11–48. · `domain/tooth/data_quality.py`, `test_fv01_provenance_guards.py`, `test_p3_anatomical_intelligence.py`. · Doctor confirmation of a true absence versus a segmentation miss. · B3, B5. · Segmentation plus optional doctor statement. · Keep the current refusal to fill the chart. · A chart gap is labeled unresolved or doctor-confirmed, never both silently. · Not a hot path. · Required. One case with a real edentulous span before acceptance of that state. · Unconfirmed absence is `NOT_AVAILABLE`, not a fact. · Flag source.

### B16. Derived anatomy classification
`IMPLEMENTED_BUT_PARTIAL` · Provenance enum and intelligence truth states exist. They are not the unified class list. · `domain/case/provenance.py`, `test_fv01_provenance_guards.py`. · Map every anatomy object onto the master-plan classes. · Section 5 of the master plan. · All anatomy objects. · Existing enums; extend rather than parallel a second hidden vocabulary. · A serialized tooth carries one primary class. · Not a hot path. · Required. · Classification is not clinical approval. · Class and algorithm on the object.

### B17. Virtual roots
`NOT_IMPLEMENTED` · No virtual-root mesh generator. CBCT roots are refused for crown STL. · Root-bone tests assert the refusal. · Optional derived roots, visually distinct, excluded from "observed anatomy" exports. · B8, H. · A rule or a library, plus the crown. · None selected. · If absent, the UI says so. If present, class is `DERIVED_GEOMETRY`. · Unmeasured. · Not required for STL-only acceptance. · Virtual roots cannot drive a bone claim. · Generator version and parent crown.

### B18. Reconstructed geometry
`NOT_IMPLEMENTED` · No crown completion or scan-hole reconstruction. · None. · A reconstructed surface with a parent region and a doctor accept. · A11, B6. · Incomplete observed surface. · Kernel trial in FV-11. · Reconstructed faces are queryable apart from observed faces. · Must not be free on the UI thread. · Only when a real scan needs it. · `RECONSTRUCTED`, never `OBSERVED`. · Parent faces and parameters.

### B19. Truth and provenance classification
`IMPLEMENTED_BUT_PARTIAL` · Several honest enums, listed in the master plan. Export hashes and job hashes exist. · Provenance tests across WP-01–WP-10. · One class list and one chain. · Master plan section 5. · Every clinical object. · Existing dataclasses. · New objects cannot be saved without a class. · Negligible. · Required. · `VERIFIED` is not a default. · See master plan section 5.2.

---

## C. Professional 3D CAD interaction

### C1. Orbit, pan, zoom
`IMPLEMENTED_AND_VERIFIED` · `OrbitControls` in `StageViewer.tsx`. · Viewer and toolbar tests; wave e2e uses the real viewer with mocked cases. · Input mapping review on a real mouse and trackpad during FV-DESK. · None. · A scene. · Three.js. · The control does not steal a gizmo drag. · Frame time unmeasured. · Exercise on the official mesh in FV-PERF. · Navigation is not a clinical measurement. · Camera state is presentation.

### C2. Standard views
`IMPLEMENTED_AND_VERIFIED` · Presets for occlusal, front, and lateral. · `cameraNavigation.ts`, interaction tests. · Presets should follow the reviewed scan orientation once A5 exists. · A5 later. · Current mesh axes. · Existing presets. · Preset buttons match the documented directions. · Tween exists; duration unbudgeted. · Required on a real case. · Views are not occlusal-plane truth until orientation is reviewed. · Presentation.

### C3. Camera presets
`IMPLEMENTED_AND_VERIFIED` · Reset and preset commands. An orientation-cube helper table exists without a cube widget. · Wave 4 presentation tests. · Either build a cube or stop describing the helper as a cube. · C2. · None. · Existing commands. · Keyboard and toolbar hit the same command. · Unmeasured. · Required. · None clinical. · Presentation.

### C4. Fit and isolate
`IMPLEMENTED_AND_VERIFIED` · Fit case, arch, and selection; isolate hides other teeth. · `fitTargets.ts`, `wp03Workspace.test.ts`. · Fit must include visible attachments and pontics when those exist. · C1. · Bounds of visible meshes. · Existing fit math. · Isolate round-trips with the selection. · WP-12 client tests check visibility toggles without BVH rebuild. · Required. · Isolate is presentation. · Presentation.

### C5. Tooth picking
`IMPLEMENTED_AND_VERIFIED` · BVH raycast, `toothKey` on mesh user data. · `picking.ts`, workspace foundation tests. · Picking of attachments, pontics, and gingiva as separate object types. · B2. · Render meshes. · three-mesh-bvh. · Pick hits the visible tooth, including after a stage change. · Formal frame-time budget still required on the full official scene. · Required. · Pick identity uses `tooth_ref`. · Selection is UI state plus the tooth id.

### C6. Hover
`IMPLEMENTED_AND_VERIFIED` · Pointer move sets hover style. · StageViewer and dental-map behavior covered by interaction tests. · Hover readouts for measurement once C15 exists. · C5. · Same as pick. · Existing materials. · Hover does not change the plan. · Must stay cheap. Measure. · Required. · Hover is presentation. · Not persisted.

### C7. Multi-selection
`IMPLEMENTED_BUT_PARTIAL` · Shift/Ctrl adds keys. Group inspector exists. No group transform. · `useToothSelection.ts`, wave 10 inspector tests. · Group transform and a visible selection set. · C5, D8. · Tooth keys. · Existing selection owner. · Reload of a stage keeps the set (`preserveSelectionAcrossTeeth`). · Unmeasured. · Required. · Multi-select is not anchorage. · Selected `tooth_ref` list.

### C8. Lasso or box selection
`NOT_IMPLEMENTED` · No marquee or lasso. · None. · Add if FV-04 shows multi-select is too slow for a full arch. · C7. · Screen-space picks. · three-mesh-bvh. · Selected set matches a reference pick list on a fixture scene, then on a real case. · Must not block orbit. · Required only if the phase exit says so. · Selection is not a diagnosis region. · Resulting tooth set.

### C9. Transform gizmos
`IMPLEMENTED_BUT_NOT_WORLD_CLASS` · `TransformControls` translate/rotate in treatment setup and refinement. · `StageViewer.tsx`, `wp04ToothInteraction.test.ts`. · Tooth-frame or arch-frame gizmo, not only world axes. · C11, B11. · Selected tooth. · Three.js TransformControls. · A gizmo drag equals the numeric delta within a stated epsilon. · Unmeasured on dense meshes. · Required. · World-axis motion is not tip/torque. · Edit transaction id.

### C10. Numeric transforms
`IMPLEMENTED_AND_VERIFIED` · Inspector numeric fields apply movement. · `InspectionPanel.test.tsx`, `test_wp04_tooth_interaction.py`. · Units and frame labeled as computed until clinical axes exist. · D3. · Movement record. · Existing edit API. · Numeric apply, undo, and API payload agree. · Not a hot path. · Required. · Numbers are plan deltas, not outcomes. · `DoctorMovementEdit`.

### C11. Constrained movement
`IMPLEMENTED_BUT_PARTIAL` · Constraints report `NOT_CONFIGURED`. The gizmo is not clamped. · `domain/movement/interaction.py`, setup readiness tests. · Doctor-configurable clamps that the gizmo and the numeric fields both honor. · D4. · Preference values. · Existing constraint status field. · A value past the limit is rejected or explicitly overridden and recorded. · Not a hot path. · Required. · A limit is a preference, not a biological constant, unless a cited rule is attached. · Preference version on the edit.

### C12. Rotation
`IMPLEMENTED_BUT_NOT_WORLD_CLASS` · Rotation is part of 6-DOF and the gizmo rotate mode. · Planning and interaction tests. · Rotation about a named axis (long axis versus geometric). · B10, C9. · Tooth frame. · Existing movement model. · Axis of rotation is stored, not only a matrix. · Unmeasured. · Required. · Geometric rotation is not clinical rotation. · Axis id and degrees.

### C13. Translation
`IMPLEMENTED_BUT_NOT_WORLD_CLASS` · Translation in the local movement record and world gizmo. · Same as C12. · Mesial-distal, buccal-lingual, intrusion-extrusion as labeled components when a frame exists. · B11, C9. · Tooth frame. · Existing `ToothMovement`. · Components sum to the stored translation. · Unmeasured. · Required. · Names of clinical directions stay unavailable without a frame. · Component list and frame id.

### C14. Undo and redo
`IMPLEMENTED_AND_VERIFIED` · Client stacks and API edit application. Inspector owns the buttons. · `p8Workflow.test.tsx`, `test_doctor_editing_phase9.py`, wave 10 ownership tests. · Undo of segmentation edits, IPR, attachments, and stage locks when those exist. · D14. · Edit log. · Existing stacks. · Undo restores the previous version hash. · Not a hot path. · Required. · Undo is not a clinical reversal of a printed appliance. · Edit history.

### C15. Measurement
`PLACEHOLDER` · Toolbar copy says no measurement tool is active. Overlay capability is off. · `featureDepth.test.ts` guards honesty. · Distance and angle on meshes, with a truth label. · C5. · Mesh points. · three-mesh-bvh closest-point. · A known synthetic distance is recovered within a stated epsilon, then repeated on a real crown pair. · Must be interactive. Budget after baseline. · Required for a CAD claim. · A distance is `COMPUTED`, not IPR. · Points, frame, and value.

### C16. Cross-section
`NOT_IMPLEMENTED` · Section overlay marked unavailable. · Overlay architecture tests. · One clipping plane with a read-out, if FV-04 keeps it in scope after a workflow check. · C1. · Display meshes. · Three.js clipping. · Section does not alter exported meshes. · Display-only. · Optional until the phase says otherwise. · Section is `PRESENTATION_ONLY`. · Plane parameters, not a medical slice.

### C17. Scene and layer control
`IMPLEMENTED_BUT_PARTIAL` · Layer groups for teeth, gingiva, occlusion, measurement, validation. Several stay hidden. Toggles exist for gingiva, wireframe, labels. · `sceneHierarchy.ts`, `wp03Workspace.test.ts`. · A layer list that matches objects which actually exist, including future shells. · C1. · Scene graph. · Existing registry. · Hidden layers are excluded from picking. · Visibility toggle must not rebuild BVH (already a WP-12 client test intent). · Required. · Hidden is not deleted. · Layer visibility is presentation.

### C18. Occlusion visualization
`NOT_IMPLEMENTED` + `NOT_AVAILABLE_BY_DATA` · Occlusion layer is not shown. Analysis text says unavailable. · `test_wp08_occlusion_advanced_anatomy.py`, feature-depth tests. · Color map only after a registration exists. · I1. · Registered arches. · Existing layer slot. · With no registration, the layer stays off and the reason is visible. · Unmeasured. · Required on a bite case; the no-bite path is the default acceptance path. · Colors are not a clinical contact diagnosis. · Registration id or `NOT_AVAILABLE`.

### C19. Contact visualization
`NOT_IMPLEMENTED` · Contact material profiles exist and are not applied in the scene. · `materialProfiles.ts`. · Paint geometric contacts from the validation report. · L3, C17. · Validation pairs. · Existing materials. · Viewport pair ids match the report. · Must not require a second proximity pass if the report is current. · Required once contacts are computed. · `GEOMETRIC_CONTACT` only. · Finding id.

### C20. Collision visualization
`NOT_IMPLEMENTED` · Collision counts render as text in the validation panel. · `ValidationPanel.test.tsx`, `test_p0_2_validation_reconciliation.py`. · Mesh highlighting for colliding pairs. · L2, C17. · Validation collisions. · three-mesh-bvh or the engine's pair list. · Counts in the panel equal highlighted pairs. · Official upper validation found 0 collisions and 39 proximities in the WP-12 sample. Highlighting that set must be cheap. · Required. · Highlight is not a clinical interference score. · Finding id.

### C21. Treatment overlays
`IMPLEMENTED_AND_VERIFIED` · Target ghost and centroid movement lines. · Wave 4 tests, StageViewer. · Overlays for IPR, attachments, and collisions as those systems grow. · D2. · Source and target meshes. · Existing treatment layer. · Ghost uses target vertices, not a second invented tooth. · Unmeasured. · Required. · Ghost is `SIMULATED` or `DERIVED_GEOMETRY`. · Setup version id.

### C22. Stage timeline
`IMPLEMENTED_BUT_NOT_WORLD_CLASS` · Slider, markers, play. · `StageTimeline.test.tsx`, staging tests. · Per-tooth bars, comparison, and a table (J18–J20). · J1. · Stage list. · Existing component. · Selected index matches the mesh on screen. · Stage change cost unmeasured on the official scene. · Required. · Playback is `SIMULATED`. · Stage id.

### C23. Selection persistence
`IMPLEMENTED_AND_VERIFIED` · Selection survives a tooth-list reload; case and workspace restore from session storage. · `useToothSelection.ts`, `caseWorkspacePersistence.test.ts`, `p8Workflow.test.tsx`. · Persist selection inside the treatment session, not only the browser tab. · O7. · Tooth keys. · Existing helper. · Refresh keeps the case, the step, and a valid selection or a clear empty state. · Not a hot path. · Required. · Restored selection is not a new clinical decision. · Tooth keys and workspace id.

### C24. Keyboard and mouse
`IMPLEMENTED_AND_VERIFIED` · Shortcuts for escape, fit, home, views, undo/redo. Click versus drag uses a 5 px threshold. · `interaction/model.ts` tests, toolbar tests. · Shortcuts for tools added later, with a visible map. · C1, C14. · None. · Existing matcher. · No shortcut has two owners. · Not a hot path. · Required. · Shortcuts do not bypass validation. · Command id.

### C25. CAD-grade responsiveness
`IMPLEMENTED_BUT_NOT_PROVEN` · BVH is on. Buffers build synchronously. Validation isolation helps the server and does not make the viewport incremental. · `wp03Performance.test.ts`, `wp12Performance.test.ts` (micro checks). WP-12 server numbers in the master plan. · A measured interaction budget and a non-blocking load path. · FV-PERF. · Official case meshes. · Current stack first. · Pick and stage change stay responsive while a validation job runs. · Baseline not yet stored for frames. Server validation 105.7–214.5 s is the warning. · Required. · Speed work cannot drop collisions. · Benchmark record next to the change.

---

## D. Treatment planning

### D1. Initial setup
`IMPLEMENTED_AND_VERIFIED` · Source tooth state is immutable and separate from the target. · `test_wp05_treatment_setup.py`, `test_treatment_planning_phase5.py`. · None for the source snapshot itself. · B2. · Segmented crowns. · `TreatmentPlanningEngine`. · Source hash stable across edits. · Setup median 1.39 s in WP-12. · Required. · Initial state is `SEGMENTED`, not a treatment goal. · Source mesh hashes.

### D2. Target setup
`IMPLEMENTED_AND_VERIFIED` · Target vertices from tooth-frame movements. · Same tests as D1. · Arch-form and group edits that write the same target model. · D3. · Source plus movements. · Existing engine. · Final stage of linear mode matches the target. · Included in the 1.39 s setup figure. · Required. · Target is `PLANNED` only after doctor acceptance; until then `PROPOSED` or `COMPUTED`. · Setup version id.

### D3. 6-DOF movement
`IMPLEMENTED_BUT_NOT_WORLD_CLASS` · `ToothMovement` stores translation, rotation, and intrusion/extrusion components. · `test_wp04_tooth_interaction.py`. · Clinical names only with a clinical frame. · B11. · One tooth. · Existing domain model. · Round-trip of all six components. · Unmeasured per drag. · Required. · Components are geometric. · Movement record and frame.

### D4. Movement limits
`NOT_IMPLEMENTED` · Status is not configured. · Readiness assertions in setup and staging tests. · Configurable per-tooth and per-stage limits. · C11, J3. · Doctor preferences. · New preference object. · Staging reads the same preference version the setup used. · Not a hot path. · Required. · Defaults, if any, are labeled preferences. · Preference id.

### D5. Movement types
`IMPLEMENTED_BUT_PARTIAL` · Fields exist for translation, rotation, intrusion, and extrusion. Tip and torque are not distinct clinical operations. · Planning tests. · Named operations that decompose into the 6-DOF record in a stated frame. · D3, B10. · A frame. · Existing movement struct. · Each named operation has a deterministic 6-DOF image. · Not a hot path. · Required for the vocabulary; clinical meaning waits on the frame. · The decomposition is `COMPUTED`. · Operation name and frame.

### D6. Arch expansion and contraction
`NOT_IMPLEMENTED` · No width edit. Descriptive arch measures exist. · Arch analysis tests cover description only. · A width or curve edit that moves a group and versions the setup. · B13, D8. · Arch curve. · New editor on current setup versions. · Expansion amount is recoverable from the version diff. · Unmeasured. · Required. · The number is a plan delta. · Version diff.

### D7. Arch-form editing
`NOT_IMPLEMENTED` · No curve editor. · None. · Direct manipulation of the arch curve with symmetric and asymmetric modes. · B13, C9. · Curve plus teeth. · Viewport. · Teeth store the curve version they were projected from. · Must be interactive. Budget later. · Required. · Curve is `PLANNED` after accept. · Curve version.

### D8. Group movement
`NOT_IMPLEMENTED` · Multi-select does not apply one transform. · Selection tests. · One transaction for many teeth, undoable as one. · C7, D3. · Selected set. · Existing edit transaction. · Partial failure rolls back the group. · Unmeasured. · Required. · Group motion is not evidence of anchorage. · Member list and transaction id.

### D9. Anchorage
`NOT_IMPLEMENTED` · Lock exists as "do not move," which is only a start. · `test_p4_doctor_refinement.py`. · A record of which teeth resist which movements, used by staging. · D4, J9. · Doctor designation. · Lock flag today. · A locked tooth has zero motion unless the doctor overrides and the override is stored. · Not a hot path. · Required before staging claims sequencing. · Anchorage is `PLANNED`, not a force measurement. · Lock reason.

### D10. Movement dependencies
`NOT_IMPLEMENTED` · Stale flags exist when setup changes. There is no "this tooth waits on that tooth" rule. · Staging freshness tests. · Explicit dependency edges the stager honors. · J8. · Doctor or rule. · New graph on the plan. · A cycle is rejected. · Not a hot path. · Required for sequencing claims. · Edges are plan data. · Edge list and author.

### D11. Treatment alternatives
`IMPLEMENTED_BUT_PARTIAL` · Deterministic perturbations can be generated and blocked by validation. Model adapters are unavailable. · `test_p6_advanced_planning_intelligence.py`. · Doctor-visible alternatives with a diff against the current version. · E14, L1. · Current setup. · `AdvancedPlanningIntelligenceEngine`. · No alternative becomes current without a selection and a validation result. · Unmeasured as a set. · Required. · Alternatives are `PROPOSED`. · Candidate id and validation id.

### D12. Plan versions
`IMPLEMENTED_AND_VERIFIED` · Immutable setup snapshots, compare, restore. · `engines/planning/setup_versioning.py`, `test_wp05_treatment_setup.py`. · Versions for segmentation and manufacturing as those appear. · D2. · Setup document. · Existing snapshot code. · Restore returns the stored hash. · Not separately timed. · Required. · A version is not approval. · Version id and parent.

### D13. Snapshots
`IMPLEMENTED_AND_VERIFIED` · Setup version snapshots are the snapshot mechanism. · Same as D12. · User-named bookmarks if the workflow needs them; otherwise document that versions are the snapshots. · D12. · Version store. · Existing. · A named bookmark, if added, points at an immutable version. · Not a hot path. · Required in the form of versions. · Bookmark is not a new plan. · Pointer to version id.

### D14. Doctor edits
`IMPLEMENTED_AND_VERIFIED` · Edit, reset, recalculate, reasons. · `test_doctor_editing_phase9.py`, `test_p4_doctor_refinement.py`. · Edits of IPR, attachments, stages, and segmentation. · API treatment routes. · Doctor input. · `engines/planning/editing.py`. · Source geometry unchanged by an edit. · Included in session costs. · Required. · An edit is not clinical approval unless recorded as such. · `DoctorMovementEdit` with reason.

### D15. Audit history
`IMPLEMENTED_BUT_PARTIAL` · Edit history and export JSON. No single timeline across segmentation, IPR, and export. · Doctor-editing tests; export tests. · One case history the doctor can read. · D14, N5. · Stored events. · Existing history. · History survives restart. · Not a hot path. · Required. · History is not a legal record until FV-DESK says how it is stored. · Ordered events with actor and time.

---

## E. Treatment intelligence

### E1. Movement feasibility
`NOT_IMPLEMENTED` · No feasibility score. Limits are unconfigured. Validation can show collisions after the fact. · Validation tests show post-hoc geometry, not feasibility. · A deterministic check against configured limits and collisions, labeled `COMPUTED`. · D4, L2. · Plan plus limits. · Validation engine, not a new hidden score. · Infeasible motion cannot be silently staged. · Must be incremental once validation is too slow. · Required. · Feasibility is not a promise of tooth movement in a patient. · Check id and inputs.

### E2. Movement dependencies
`NOT_IMPLEMENTED` · Same gap as D10. · None beyond stale flags. · Shared model with D10. · D10. · Plan graph. · One implementation. · Setup and staging read the same edges. · Not a hot path. · Required. · Dependencies are plan logic. · Edge provenance.

### E3. Collision-aware planning
`NOT_IMPLEMENTED` · Collisions are reported after staging. They do not move teeth. · `test_geometric_validation_phase7.py`. · Proposals that avoid a collision, then go through validation again. · L2, E14. · Stage meshes. · Geometric engine as the checker. A planner may propose. · The checker can reject the proposal. · Reuse pair results. Do not add a second collision code path without a comparison. · Required. · Avoidance is `PROPOSED`. · Proposal id and validation id.

### E4. Space-aware planning
`NOT_IMPLEMENTED` · Centroid gaps are not a space model. · IPR tests show the centroid method. · Space from contact regions (F1) used as a constraint. · F1. · Meshes. · Validation proximity. · Space sign and magnitude have a defined geometric meaning. · Unmeasured. · Required. · Space is `COMPUTED`. Closing it is `PLANNED`. · Region id.

### E5. Tooth-to-tooth interactions
`IMPLEMENTED_BUT_PARTIAL` · Intra-arch proximity and collision pairs. · `test_p0_4_intra_arch_validation.py`. · Use those pairs in planning and IPR, not only in a report. · L2, L3. · Stage meshes. · Geometric engine. · Cross-arch pairs stay out of staging collisions unless registration exists. · Pair metrics have a vectorized test. Full upper validation is still minutes. · Required. · Interaction is geometric. · Pair ids.

### E6. Arch coordination
`NOT_IMPLEMENTED` · Two arches can be presented. Their motions are not coordinated. · Two-arch presentation tests. · A rule, doctor-set, for midline, occlusal plane, or class, applied only when the data exists. · I6, D7. · Both arches and optional bite. · None yet. · With no bite, coordination that needs bite stays `NOT_AVAILABLE`. · Unmeasured. · Required for dual-arch claims. · Coordination is `PLANNED`. · Rule id and missing inputs.

### E7. Movement sequencing
`NOT_IMPLEMENTED` · All teeth interpolate together. · Staging engine source. · Ordered groups and per-tooth timing. · J5, J6. · Dependencies. · New stager beside the linear oracle. · Linear mode remains available and bit-comparable. · Unmeasured. · Required. · Sequence is not proven optimal. · Sequence version.

### E8. Overcorrection
`NOT_IMPLEMENTED` · No overcorrection stage. · None. · Doctor-set extra motion on named teeth at the end of the series. · J10. · Preferences. · Staging engine. · Overcorrection stages are labeled and removable. · Unmeasured. · Required if staging claims finishing control. · Overcorrection is `PLANNED`, not a prediction of relapse. · Amount and teeth.

### E9. Synergistic movements
`NOT_IMPLEMENTED` · No coupled-motion model. · None. · Only as an explicit doctor rule or a reviewed proposal. · E14. · Doctor or a documented rule. · Do not invent a biomechanics engine. · Any automatic coupling is `PROPOSED` and validated. · Unmeasured. · Optional until a rule is specified. · Not a force model. · Rule id.

### E10. Antagonistic movements
`NOT_IMPLEMENTED` · No detector for opposing planned motions beyond collisions. · None. · Report opposing translations on neighbors as findings. · E5. · Movements. · Deterministic comparison. · Findings do not auto-edit the plan. · Cheap compared with mesh collision. · Required as a warning, not as a solver. · Warning is `COMPUTED`. · Finding id.

### E11. Anchorage logic
`NOT_IMPLEMENTED` · Lock flag only. · Refinement tests. · Staging consumes D9. · D9, J9. · Locks. · Stager. · A dependent tooth does not move before its anchorage step unless overridden. · Unmeasured. · Required with sequencing. · Logic is plan data. · D9 record.

### E12. Configurable movement constraints
`NOT_IMPLEMENTED` · Environment stage count exists. Per-tooth clinical constraints do not. · Staging readiness marks constraints unavailable. · Preference document shared by setup and staging. · D4. · Doctor. · Case preferences. · Changing a constraint marks stages stale. · Not a hot path. · Required. · Constraints are not universal clinical law. · Preference version.

### E13. Doctor-configurable preferences
`NOT_IMPLEMENTED` · No preference profile. · None. · Attachments, IPR, rates, and overcorrection read one profile. · E12, G8. · Doctor. · Local settings with the case. · A case stores the profile version used. · Not a hot path. · Required. · Preferences are not patient findings. · Profile id.

### E14. Model-assisted proposals
`REQUIRES_EXTERNAL_TECHNOLOGY` · STTAlign, TADPM, and 3DTeethSAM adapters raise. Deterministic perturbations exist instead. · `test_p6_advanced_planning_intelligence.py`; evaluation JSON `not_run`. · A challenger trial on real cases before any default changes. · FV-MODEL, L1. · Real cases. · Existing adapters, still unavailable. · A proposal that fails validation cannot be selected. · Unmeasured. · Required before a model is the default. · Output is `PROPOSED`. · Model hash and parameters.

### E15. Deterministic validation around every proposal
`IMPLEMENTED_AND_VERIFIED` · Intelligence engine routes candidates through geometric validation. · `test_p6_advanced_planning_intelligence.py`. · The same gate for future attachment, IPR, and staging proposals. · L1. · Candidate geometry. · `GeometricValidationEngine`. · A failing candidate has a stored result and is not current. · Uses the same expensive validation path. · Required. · PASS is technical. · Validation report id.

---

## F. IPR, space, and contact intelligence

### F1. Contact-region detection
`NOT_IMPLEMENTED` · Contacts in validation are pair findings, not surface regions. IPR uses centroids. · `engines/planning/proposals.py`, geometric validation tests. · A region (faces or points) per neighboring pair. · L3. · Crown meshes. · Extend the geometric engine; do not add an uncompared second method. · Region distance matches a fixture with a known gap. · Must be cheaper than a full revalidation when only one tooth moves. Target set in FV-PERF. · Required. · Region is `COMPUTED`. · Pair id and algorithm version.

### F2. Interproximal regions
`NOT_IMPLEMENTED` · Neighbors are adjacent in a centroid list. · Proposal tests. · Anatomical neighbor relation along the arch, with unresolved identity still handled. · B14, F1. · Arch order. · Arrangement plus proximity. · A missing neighbor is `NOT_AVAILABLE`, not zero IPR. · Unmeasured. · Required. · Neighbor relation is `COMPUTED`. · Tooth pair and arch.

### F3. Collision regions
`IMPLEMENTED_BUT_PARTIAL` · Collisions are counted per pair. The region is not returned for display. · `test_geometric_validation_phase7.py`, WP-12 sample had 0 collisions. · Face sets for the viewport. · L5, C20. · Stage meshes. · Existing engine. · A constructed intersection is detected and located. · Part of the minute-scale validation. · Required. · Collision is geometric. · Finding id.

### F4. Clearance
`IMPLEMENTED_BUT_PARTIAL` · Proximity counts and thresholds exist. · `test_geometric_validation_phase7.py` (39 proximities on the WP-12 upper sample). · Clearance as a distance on the contact region, distinct from a prescription. · F1. · Meshes and a threshold. · Existing threshold config. · Threshold changes do not rewrite doctor-entered IPR. · Same cost class as validation. · Required. · Clearance is `COMPUTED`. · Threshold version.

### F5. IPR proposal
`IMPLEMENTED_BUT_NOT_WORLD_CLASS` · Centroid-distance delta, status needs review, clinical-review warning on every site. · `test_proposal_engine_phase10.py`, `test_wp07_clinical_tools.py`. · Proposals from F1, still non-prescriptive. · F1. · Setup positions. · Replace centroid metric after a comparison on the official case. · A proposal shows amount, method, and "not a prescription." · Unmeasured separately. · Required. · Class `PROPOSED`. · Method id. Centroid method must stay visible until removed.

### F6. Doctor-entered IPR
`IMPLEMENTED_BUT_PARTIAL` · PATCH can set status and amount. · `test_wp07_clinical_tools.py`. · Entry in the viewport on a contact, with lock. · F2, C15. · Doctor. · Existing clinical-tools value source `DOCTOR_ENTERED`. · Entered amount is not overwritten by regenerate. · Not a hot path. · Required. · Doctor entry is `PLANNED` only after they confirm. · Source enum and user.

### F7. IPR locking
`NOT_IMPLEMENTED` · No lock distinct from status. · None. · A lock flag staging and auto-adjust must honor. · F6. · Doctor. · Clinical tools model. · A locked site survives restage. · Not a hot path. · Required. · Lock is a decision. · Lock on the site.

### F8. IPR propagation into staging
`NOT_IMPLEMENTED` · Staging warns that IPR is not applied. · `engines/planning/staging_engine.py` limitation strings; smart-staging tests. · Stage timing of each locked or proposed site. · J15, F6. · IPR records. · Stager. · A stage without the IPR yet does not show the space as already removed. · Unmeasured. · Required. · Timing is `PLANNED`. · Stage index on the site.

### F9. IPR reports
`IMPLEMENTED_BUT_PARTIAL` · Sites serialize into the engineering export. · Export and WP-07 tests. · A doctor-readable report with method and limitations. · N6, F5. · Sites. · Export JSON today. · Report totals match the site list. · Not a hot path. · Required. · Report is not informed consent. · Export hash includes the report.

### F10. Per-contact provenance
`IMPLEMENTED_BUT_PARTIAL` · Value source enum: measured, computed proposal, doctor-entered, not available. Measurement is not actually a contact region yet. · `domain/treatment_plan/clinical_tools.py`. · Bind each site to F1 region ids. · F1. · Sites. · Existing enum. · A site without a source cannot be saved. · Not a hot path. · Required. · `MEASURED` is reserved for a real region measurement. · Source plus algorithm.

### F11. Threshold and rule configuration
`IMPLEMENTED_BUT_PARTIAL` · Validation thresholds are caller-supplied. IPR rules are not a preference profile. · Geometric validation threshold tests. · One configured rule set with a version. · E13. · Doctor or engineering defaults labeled as such. · Existing threshold arguments. · Changing a threshold restales IPR proposals. · Not a hot path. · Required. · Defaults are not clinical standards unless cited. · Config version.

### F12. IPR validation
`IMPLEMENTED_BUT_PARTIAL` · Validation 2 can mark IPR checks not available rather than pass them. · `test_wp09_validation_2.py`. · An actual consistency check once amounts and stages exist. · F8, L11. · Sites and stages. · Honesty layer stays; add a real check beside it. · A mismatch is a warning or error, never a silent pass. · Unmeasured. · Required. · Failure is technical. · Check id.

### F13. IPR visual overlays
`NOT_IMPLEMENTED` · No IPR coloring in the viewport. · Feature-depth tests forbid a fake IPR display. · Overlay from site records. · C21, F5. · Sites. · Overlay registry. · Overlay amounts match the panel. · Must be display-only. · Required. · Overlay is presentation of a classified value. · Site id.

---

## G. Attachments and auxiliaries

### G1. Attachment library
`NOT_IMPLEMENTED` · No library. · None. · Versioned solids and metadata. · G3. · Authored meshes with licenses cleared. · trimesh for storage. · A library item has an id, size parameters, and a hash. · Not a hot path. · Required. · Library geometry is `DERIVED_GEOMETRY`. · Item hash.

### G2. Attachment types
`IMPLEMENTED_BUT_NOT_WORLD_CLASS` · A site can be created with type `UNDETERMINED` when rotation or tip is nonzero. · `test_proposal_engine_phase10.py`. · Named types from G1. · G1. · Movement plus library. · Replace the undetermined placeholder. · Unknown type cannot be exported as manufacturable. · Not a hot path. · Required. · Type is `PROPOSED` until chosen. · Type id.

### G3. Attachment geometry
`NOT_IMPLEMENTED` · No attachment mesh. · Manufacturing tests say shells and related CAD are unavailable. · A solid per placement. · G1. · Library mesh plus transform. · trimesh or the chosen kernel. · Geometry hash changes when the transform changes. · Unmeasured. · Required. · Solid is `DERIVED_GEOMETRY`. · Mesh hash.

### G4. Size
`NOT_IMPLEMENTED` · No size parameter. · None. · Parametric or discrete sizes from the library. · G3. · Doctor or rule. · Library. · Size is in the export. · Not a hot path. · Required. · Size is a design choice. · Parameter value.

### G5. Position
`NOT_IMPLEMENTED` · No surface position. · None. · Point and normal on the crown. · C5, G3. · Crown mesh. · BVH closest point. · Position survives restage of the parent tooth. · Must be interactive. · Required. · Position is `PLANNED` after the doctor places it. · Surface point and tooth version.

### G6. Orientation
`NOT_IMPLEMENTED` · No attachment frame. · None. · Rotation on the surface frame. · G5. · Tooth frame. · Gizmo reuse. · Orientation stored as a quaternion or equivalent with a named convention. · Unmeasured. · Required. · Orientation is plan data. · Frame convention id.

### G7. Positive and negative configurations
`NOT_IMPLEMENTED` · No solid or void representation. · None. · Positive addition and negative relief only when the shell kernel can represent both. · G3, M10. · Library. · Manufacturing kernel after FV-11 evidence. · A negative shape cannot be exported as a tooth cavity in the scan. · Unmeasured. · Required if the library includes pressure points or windows. · Class `DERIVED_GEOMETRY` with a boolean role. · Role flag.

### G8. Automatic placement rules
`NOT_IMPLEMENTED` · The current trigger is "movement components nonzero," which is not a placement rule. · Proposal tests. · Rules from the preference profile, output `PROPOSED`. · E13, G1. · Movements and library. · Deterministic rules before any model. · The doctor can reject a rule result. · Not a hot path. · Required for automation; manual placement must exist first. · Rule output is `PROPOSED`. · Rule version.

### G9. Movement-driven proposals
`IMPLEMENTED_BUT_NOT_WORLD_CLASS` · Nonzero rotation/tip/torque creates an undetermined site. · WP-07 tests. · Proposals that name a library type and a reason. · G8. · Movement. · Replace the current trigger. · A tooth with no movement gets no attachment proposal. · Not a hot path. · Required. · Proposal is not placement. · Reason string and movement version.

### G10. Doctor adjustment
`IMPLEMENTED_BUT_PARTIAL` · Status can be accepted or rejected. Geometry cannot be adjusted. · Clinical-tools API tests. · Gizmo edit of G5 and G6. · G3, C9. · Doctor. · Edit path. · Adjustment versions the attachment and stales the shell. · Interactive budget later. · Required. · Adjustment is a doctor edit. · Edit record.

### G11. Attachment templates
`NOT_IMPLEMENTED` · No template. · None. · A saved set of types and rules. · G8, E13. · Doctor. · Preference store. · Applying a template is undoable. · Not a hot path. · Required if rules are shared across cases. · Template is not a patient plan until applied. · Template id.

### G12. Attachment persistence
`IMPLEMENTED_BUT_PARTIAL` · Proposal records persist inside the treatment session and export. · Export tests, session tests. · Persist solids and transforms, not only status. · G3, A13. · Attachment objects. · Session store. · Restart keeps the solid hash. · Not a hot path. · Required. · Persistence is not approval. · Object id.

### G13. Attachment-to-stage behavior
`NOT_IMPLEMENTED` · Staging says attachments are not applied. · Staging limitation text. · Start stage, end stage, and visibility per stage. · J14. · Doctor or rule. · Stager. · A stage mesh of the tooth does not bake the attachment unless the stage says so. · Unmeasured. · Required. · Timing is `PLANNED`. · Stage range.

### G14. Manufacturing geometry for attachments
`NOT_IMPLEMENTED` · No relief or bonded solid in the shell path. · WP-10 evidence: manufacturing not certified. · Boolean or offset the shell against G3. · M10, G7. · Attachment solid and shell. · Kernel chosen in FV-11. · Interference with the tooth is classified, not hidden. · Kernel trial required. · Required before a shell is called printable with attachments. · Result is `DERIVED_GEOMETRY`. · Boolean parameters.

### G15. Attachment validation
`IMPLEMENTED_BUT_PARTIAL` · Honesty layer can mark attachment checks not available. · `test_wp09_validation_2.py`. · Checks for missing mesh, intersection, and stage-range consistency. · G3, L12. · Attachment objects. · Validation 2 plus geometric engine. · An attachment inside a tooth is a finding. · Unmeasured. · Required. · Finding is technical. · Check id.

### G16. Indirect bonding or guide pathway
`NOT_IMPLEMENTED` · No bracket or guide objects. · None. · Decide in a plan revision whether First Version includes it. Default: tracked, not on the minimum gate. · G1. · A library and a prescription if ever in scope. · None. · If deferred, the UI does not offer it. · n/a while deferred. · Not required for the aligner gate. · Guides would be `DERIVED_GEOMETRY`. · Decision recorded in the plan changelog if scope changes.

### G17. Attachment provenance
`IMPLEMENTED_BUT_PARTIAL` · Clinical-tool truth and value source cover status. They do not cover a solid. · WP-07 tests. · Full chain once geometry exists. · B19, G3. · Attachment object. · Existing truth fields. · Export includes type, transform, author, and rule. · Not a hot path. · Required. · Acceptance is explicit. · Chain in master plan section 5.2.

---

## H. Pontics, missing teeth, and derived geometry

### H1. Virtual pontics
`NOT_IMPLEMENTED` · No pontic type in Python. · Repository search found no pontic implementation. · A pontic mesh with a stage size rule. · H8, B15. · Doctor request plus a space. · Library or mirror. · Pontic id cannot collide with a `tooth_ref` from the scan. · Unmeasured. · Required for extraction and missing-tooth presentation. · `DERIVED_GEOMETRY`. · Parent space and source tooth if any.

### H2. Tooth-library geometry
`NOT_IMPLEMENTED` · No tooth library. · None. · Licensed or originally authored crowns with stable ids. · H1. · Library files. · trimesh. · Library hash in the case file. · Not a hot path. · Required if pontics use a library. · Library mesh is not the patient. · Asset hash and license flag.

### H3. Mirrored geometry
`NOT_IMPLEMENTED` · No mirror tool. · None. · Mirror of a contralateral `tooth_ref` when that tooth exists. · B12. · A real contralateral crown. · Deterministic mirror in the arch frame. · If the contralateral tooth is missing, mirror stays `NOT_AVAILABLE`. · Unmeasured. · Required only when used. · `DERIVED_GEOMETRY`. · Source tooth and frame.

### H4. Reconstructed geometry
`NOT_IMPLEMENTED` · Same gap as B18. · None. · Shared implementation with B18. · B18. · Incomplete mesh. · FV-11 kernel. · Same acceptance as B18. · Same. · Same. · `RECONSTRUCTED`. · Parent region.

### H5. Space closure
`NOT_IMPLEMENTED` · No closure plan. Centroid IPR is not closure. · None. · A planned reduction of a gap with staged motion. · F4, J7. · A measured gap. · Stager. · Closure amount matches the sum of staged translations within tolerance. · Unmeasured. · Required for extraction cases. · Closure is `PLANNED`. · Gap id and movements.

### H6. Extraction scenarios
`NOT_IMPLEMENTED` · No extraction stage. · None. · A tooth marked extracted at a stage, with an optional pontic. · H1, J12. · Doctor decision. · Plan model. · Extracted tooth is absent from later stage meshes and present in earlier ones. · Unmeasured. · Required before extraction is offered. · Extraction is `PLANNED`, not an inferred absence. · Stage index and tooth id.

### H7. Derived gingiva and presentation geometry
`IMPLEMENTED_BUT_PARTIAL` · `syntheticGingiva.ts` builds a presentation surface when real gingiva is absent. · `syntheticGingiva.test.ts`. · Keep it presentation-only. Add observed gingiva as a different object when data exists. · A10. · Tooth centroids and a generator. · Existing generator. · Manufacturing and validation tests fail if they consume the synthetic mesh as anatomy. · Display-only. · Required to stay honest. · `PRESENTATION_ONLY`. · Generator version. Excluded from export anatomy.

### H8. Classification so derived objects cannot masquerade
`IMPLEMENTED_BUT_PARTIAL` · Fixture flags and provenance enums block some mislabeling. There is no single derived-object type. · Provenance guard tests. · A derived-object record required for pontics, mirrors, virtual roots, shells, and synthetic gingiva. · B19. · Those objects. · Domain model. · Export manifest lists class per file. · Not a hot path. · Required. · Misclassification is a product defect, not a warning to ignore. · Class on every mesh in the manifest.

---

## I. Occlusion and registration

### I1. Upper/lower registration
`NOT_IMPLEMENTED` + `NOT_AVAILABLE_BY_DATA` · Without evidence, capability state stays unavailable. Kinds reserved: explicit transform, bite scan, common frame, source metadata. · `test_wp08_occlusion_advanced_anatomy.py`, `domain/tooth/occlusion.py`. · A stored rigid transform between arches. · A4. · A bite or a doctor transform. · Open3D ICP is a candidate trial, not a dependency yet. · A case with only two crown STLs stays unavailable. · Unmeasured. · Required for any bite claim. · Registration is `COMPUTED` or doctor-accepted, and still not a clinical occlusion grade. · Transform and evidence kind.

### I2. Bite registration
`REQUIRES_REAL_DATA` · `BITE_SCAN` is an enum value with no importer. · Occlusion tests use the unavailable path. · Import a bite STL or PLY and record the result. · A2 or A1, I1. · A bite scan. · trimesh plus a registration trial. · Bite mesh hash stored. Failure leaves occlusion unavailable. · Unmeasured. · A dedicated bite case. · The bite mesh is `OBSERVED`. · File hash.

### I3. Scan-to-scan registration
`NOT_IMPLEMENTED` · No ICP or landmark alignment in product engines. · None. · A reviewed alignment between two meshes of the same arch or of arch and bite. · I4, I5. · Two meshes. · Open3D or a small in-house ICP, chosen by trial. · Residual error is stored and can fail the alignment. · Budget on the official mesh size. · Required when used. · Alignment is `COMPUTED`, `REQUIRES_REVIEW`. · Algorithm, parameters, residual.

### I4. Landmark registration
`NOT_IMPLEMENTED` · Landmarks are extrema, unsuitable as anatomical landmarks. · Intelligence tests. · Use doctor landmarks or a reviewed detector. · B9. · At least three pairs. · Rigid Procrustes. · Under-determined input stays `NOT_AVAILABLE`. · Cheap. · Required only with landmarks. · Result `COMPUTED`. · Point pairs.

### I5. Surface registration
`NOT_IMPLEMENTED` · No surface ICP. · None. · ICP or equivalent after a coarse alignment, with a failure threshold. · I3. · Overlapping surfaces. · Candidate Open3D. · A known transformed copy is recovered within a stated epsilon. · Time it on a full arch. · Required for automatic bite alignment. · Do not hide a large residual. · Residual and iteration count.

### I6. Occlusal relationships
`NOT_AVAILABLE_BY_DATA` · Relationship field stays unavailable. · WP-08 tests. · A descriptive relation only after I1. · I1. · Registered arches. · Deterministic classifier later; doctor label is enough to start. · No class or overjet number is invented. · Not a hot path. · Required on a bite case. · A number is `COMPUTED` or doctor-entered. · Method id.

### I7. Contacts
`NOT_AVAILABLE_BY_DATA` · `CLINICAL_OCCLUSAL_CONTACT` is reserved and unassigned. Geometric contact requires registration that is not available. · WP-08 and feature-depth tests. · Geometric contacts after I1, still not clinical contacts. · I1, F1. · Registered meshes. · Geometric engine, inter-arch only when registered. · Dual-arch overlap in unregistered space is not a contact (intra-arch test already guards staging). · Part of validation cost. · Required on a bite case. · Clinical contact stays unassigned until a method is accepted. · Semantics enum.

### I8. Clearance between arches
`NOT_AVAILABLE_BY_DATA` · Same gate as I7. · Same tests. · Inter-arch distance map after registration. · I1, F4. · Registered meshes. · Existing proximity code, new pair scope. · Unregistered clearance is not shown as zero. · Same cost class as validation. · Required on a bite case. · `COMPUTED`. · Registration id.

### I9. Bite shifts
`NOT_IMPLEMENTED` · No bite-shift object. · None. · A planned jaw transform distinct from tooth motion. · I1. · Doctor. · Plan model. · Tooth moves and jaw shifts do not share one matrix silently. · Unmeasured. · Optional until a case needs it. · `PLANNED`. · Shift id.

### I10. Bite stops
`NOT_IMPLEMENTED` · No bite-stop solid. · None. · An auxiliary like an attachment, with occlusal intent labeled as plan data. · G3, I7. · Doctor. · Attachment library path. · A bite stop is not an observed contact. · Unmeasured. · Optional. · `DERIVED_GEOMETRY`. · Same chain as attachments.

### I11. Occlusion visualization
`NOT_IMPLEMENTED` · See C18. · See C18. · See C18. · I7, C18. · Findings. · Viewport. · See C18. · See C18. · See C18. · Presentation of a classified finding. · Finding id.

### I12. CBCT and DICOM pathway
`NOT_IMPLEMENTED` + `REQUIRES_REAL_DATA` · No DICOM reader. · None. · Local ingest, metadata, and a refusal to treat a missing volume as segmented anatomy. · I13. · DICOM from a scanner the user has rights to use. · A library chosen in the FV-09 trial. pydicom is a candidate, not a dependency. · A case without DICOM is unchanged. · Unmeasured. · A separate CBCT case. · Volume is `OBSERVED`. · Series UID and file hashes. No silent upload to a third party.

### I13. Root and bone relationships
`NOT_AVAILABLE_BY_DATA` · Crown pathway errors. · `test_p3_anatomical_intelligence.py`, root-bone module. · Reviewed segmentations and distances to a planned root. · I12, B8. · Registered CBCT anatomy. · Slicer segmentators as a reference, not a vendored app. · Unreviewed segmentation cannot constrain staging. · Unmeasured. · CBCT case. · Distances are `COMPUTED` and `REQUIRES_REVIEW`. · Segment and registration ids.

### I14. Timepoint registration
`NOT_IMPLEMENTED` · No progress scan. · None. · A second timepoint registered to the first. · I3. · Another scan of the same patient. · Same registration stack. · Timepoints are not averaged into one mesh. · Unmeasured. · Not on the minimum two-case gate unless a progress scan is in the set. · Each timepoint is `OBSERVED`. · Timepoint id.

### I15. Planned-versus-achieved registration
`NOT_IMPLEMENTED` · No achieved-scan comparison. · None. · Register a progress scan to a planned stage and report distances. · I14, J1. · Progress scan plus a stage. · Registration plus proximity. · The report cannot say the patient "achieved" the plan without a doctor reading it. · Unmeasured. · Optional for First Version. · Distances are `COMPUTED`. · Stage id and timepoint id.

### I16. Dual-arch presence is not occlusion
`IMPLEMENTED_AND_VERIFIED` · Unavailable occlusion, explicit limitation strings, intra-arch collision scope. · `engines/occlusion/capability_engine.py`, `test_wp08_occlusion_advanced_anatomy.py`, `test_p0_4_intra_arch_validation.py`. · Keep this guard when registration is added. · I1. · Two arches. · Existing gate. · A regression test loads two arches with no bite and asserts unavailable. · Not a hot path. · Required on every case. · This guard is a product rule. · Evidence kind `NONE`.

---

## J. Staging

### J1. Linear interpolation foundation
`IMPLEMENTED_BUT_NOT_WORLD_CLASS` · Vertex and movement lerp. Algorithm name `linear_progress_interpolation`. Final equals target. · `test_treatment_staging_phase6.py`, `staging_engine.py`. · Keep as oracle while a better stager is added. · D2. · Source and target meshes. · Current engine. · Oracle hashes stay stable for the linear mode. · Median 1.53 s staging in WP-12, before validation. · Required as the baseline, not as the clinical stager. · Stages are `SIMULATED`. `clinically_approved` stays false. · Algorithm version.

### J2. Automatic stage count
`NOT_IMPLEMENTED` · Count can be configured (`ALIGNERSTUDIO_STAGE_COUNT`) and is not derived from rates. · Staging tests use an explicit count. · Count equals the max of per-tooth durations under the rate limits. · J3. · Movements and rates. · New function beside the oracle. · Same movement with a tighter rate never decreases the count. · Unmeasured. · Required. · Count is `COMPUTED` from preferences. · Rate version and count.

### J3. Movement-rate constraints
`NOT_IMPLEMENTED` · Staging result warns that limits are not applied. · Smart-staging readiness. · Per-component maximum per stage. · D4. · Preferences. · Stager. · A constructed movement that exceeds the rate adds stages. · Unmeasured. · Required. · Rates are preferences. · Preference version.

### J4. Separate upper and lower staging
`IMPLEMENTED_BUT_PARTIAL` · Both arches can exist in a plan. WP-12 did not run full dual-arch validation (`full_dual_validate_enabled: false`). · `test_p0_1_two_arch_presentation.py`. · Independent stage counts with a shared timeline for review. · J2, A4. · Both arches. · Stager. · Changing the upper rate does not rebuild the lower unless a link says so. · Dual-arch validation is unmeasured. · Required. · Separate counts are plan data. · Per-arch stage lists.

### J5. Macro-staging
`NOT_IMPLEMENTED` · No layers or phases. · None. · Named phases that contain micro-stages. · J6. · Doctor groups. · Plan model. · A phase can be locked. · Unmeasured. · Required for sequencing claims. · Phase is `PLANNED`. · Phase id.

### J6. Micro-staging
`NOT_IMPLEMENTED` · Linear steps are uniform, not per-tooth micro-stages. · Staging tests. · Per-tooth timing inside a phase. · J3, J5. · Rates. · Stager. · A tooth can start after stage 0. · Unmeasured. · Required. · Timing is `PLANNED`. · Start and end indices.

### J7. Group sequencing
`NOT_IMPLEMENTED` · No groups. · None. · D8 groups mapped onto phases. · D8, J5. · Groups. · Stager. · Group order is visible in the table. · Unmeasured. · Required. · Order is `PLANNED`. · Group ids.

### J8. Movement dependencies in staging
`NOT_IMPLEMENTED` · See D10. · None. · Stager reads D10. · D10. · Edges. · Stager. · A violated edge is a validation finding. · Unmeasured. · Required. · Finding is `COMPUTED`. · Edge id.

### J9. Anchorage in staging
`NOT_IMPLEMENTED` · Locks exclude a tooth from motion. They do not sequence others. · Refinement tests. · J6 honors D9. · D9. · Locks. · Stager. · Locked tooth trajectory is identity. · Unmeasured. · Required. · Lock is `PLANNED`. · D9 id.

### J10. Overcorrection
`NOT_IMPLEMENTED` · See E8. · None. · Extra final stages, labeled. · E8. · Preferences. · Stager. · Linear oracle mode emits none. · Unmeasured. · Required with E8. · Labeled `PLANNED`. · E8 id.

### J11. Stage reordering
`NOT_IMPLEMENTED` · Stages are a generated sequence. · None. · Reorder that either regenerates or becomes a doctor override with a warning. · J1. · Stage list. · Stager. · Reorder marks validation stale. · Unmeasured. · Required if the doctor can edit timing. · Override is a doctor edit. · Previous order hash.

### J12. Stage locking
`NOT_IMPLEMENTED` · No per-stage lock. Tooth lock is different. · None. · A locked stage is not regenerated. · J11. · Doctor. · Versioning. · Regenerate copies locked stages forward. · Unmeasured. · Required. · Lock is `PLANNED`. · Stage id.

### J13. Doctor stage edits
`IMPLEMENTED_BUT_PARTIAL` · Doctor edits the target and restages. Intermediate stages are not edited. · `test_p4_doctor_refinement.py`. · Direct edit of an intermediate stage, flagged as an override. · J1, D14. · A stage. · Edit engine. · An override is visible beside the generated value. · Restage cost is in the session compose number when followed by validation. · Required. · Override is a doctor edit, not a new optimum. · Stage and edit id.

### J14. Attachment timing
`NOT_IMPLEMENTED` · See G13. · Staging warnings. · Consume G13. · G13. · Attachments. · Stager. · Tooth trajectory and attachment visibility are separate channels. · Unmeasured. · Required. · Timing `PLANNED`. · G13 id.

### J15. IPR timing
`NOT_IMPLEMENTED` · See F8. · Staging warnings. · Consume F8. · F8. · IPR sites. · Stager. · Space appears only from the scheduled stage onward. · Unmeasured. · Required. · Timing `PLANNED`. · Site id.

### J16. Collision and contact consequences
`IMPLEMENTED_BUT_PARTIAL` · Validation runs on stages. Results do not change the stage. · `test_wp09_validation_2.py`. · Show consequences and allow a proposal to restage. Do not silently move teeth. · E3, L2. · Stage meshes. · Validation engine. · A collision leaves the stage hash unchanged until the doctor edits. · Validation dominates cost. · Required. · Consequence display is `COMPUTED`. · Report id.

### J17. Stage-by-stage validation
`IMPLEMENTED_BUT_NOT_WORLD_CLASS` · Each stage can be checked. The official sample used 3 stages and one arch and took minutes. · `test_geometric_validation_phase7.py`, WP-12 JSON. · Incremental checks with the same results as a full run. · L1, FV-PERF. · All stages. · Geometric engine. · Report ids match between full and incremental runs. · 214.5 s in-process / 105.7 s isolated for the cited workload. · Required on both arches. · PASS is technical. · Report per stage.

### J18. Timeline visualization
`IMPLEMENTED_BUT_NOT_WORLD_CLASS` · See C22. · Stage timeline tests. · Per-tooth bars and IPR/attachment markers. · C22, F8, G13. · Stage and site lists. · Timeline component. · Markers match scheduled stages. · Unmeasured. · Required. · Presentation of plan data. · Stage ids.

### J19. Stage comparison
`NOT_IMPLEMENTED` · One stage is shown. Ghost is source versus target, not stage versus stage. · None. · Two-stage compare, including a difference read-out. · C21, C15. · Two stage meshes. · Viewport. · Compared meshes are the stored stage hashes. · Must not duplicate full mesh copies without a memory note. · Required. · Difference is `COMPUTED`. · Both stage ids.

### J20. Stage table
`NOT_IMPLEMENTED` · No table of per-tooth components per stage. · None. · A table bound to the same records as the viewport. · J6, P20. · Stage movements. · UI. · Editing a cell is a J13 override. · Virtualize long tables. · Required. · Cells are plan data. · Cell provenance.

### J21. Stage export
`IMPLEMENTED_AND_VERIFIED` · Stage meshes go into the hashed ZIP as treatment geometry. · `test_treatment_export_phase11.py`, `test_p0_3_export_integrity.py`. · Manufacturing meshes are a different export set (N2). · N11. · Stage meshes. · `TreatmentExportEngine`. · Exported stage hash matches the session mesh. · Export of the WP-10 evidence run cited 34.7 s. · Required. · Exported stages are `SIMULATED`, not shells. · Manifest hash.

---

## K. Simulation and derived treatment geometry

### K1. Target teeth
`IMPLEMENTED_AND_VERIFIED` · Target vertex buffers from the setup. · Planning tests, ghost overlay. · Class label on the buffer. · D2. · Movements. · Planning engine. · Target hash stable for a version. · Inside the 1.39 s setup. · Required. · `DERIVED_GEOMETRY`. · Setup version.

### K2. Intermediate stages
`IMPLEMENTED_BUT_NOT_WORLD_CLASS` · Lerp buffers. · Staging tests. · Same meshes produced by the future stager, still classified. · J1. · Stager. · Staging engine. · Linear mode remains reproducible. · 1.53 s cited for staging. · Required. · `SIMULATED`. · Stage index and algorithm.

### K3. Aligner envelope
`NOT_IMPLEMENTED` · Manufacturing boundary marks shells unavailable. · `test_p5_validation_manufacturing_export.py`, WP-10 evidence JSON. · The shell from FV-11. · M1. · Stage teeth plus offsets. · Kernel trial. · Envelope is not the tooth mesh. · Unmeasured. · Required. · `DERIVED_GEOMETRY`. · Offset parameters.

### K4. Attachment derived geometry
`NOT_IMPLEMENTED` · See G3. · None. · See G3. · G3. · Library. · See G3. · See G3. · See G3. · See G3. · `DERIVED_GEOMETRY`. · G3 hash.

### K5. Pontic derived geometry
`NOT_IMPLEMENTED` · See H1. · None. · See H1. · H1. · Library or mirror. · See H1. · See H1. · See H1. · See H1. · `DERIVED_GEOMETRY`. · H1 id.

### K6. Virtual roots
`NOT_IMPLEMENTED` · See B17. · None. · See B17. · B17. · Crown plus a rule. · None selected. · See B17. · See B17. · Not on the STL-only gate. · `DERIVED_GEOMETRY` unless CBCT-segmented. · B17 chain.

### K7. Gingival presentation
`IMPLEMENTED_BUT_PARTIAL` · See H7. · Synthetic gingiva tests. · Keep out of K3. · H7. · Generator. · Existing. · A test asserts the shell builder refuses the presentation mesh. · Display-only. · Required. · `PRESENTATION_ONLY`. · H7 version.

### K8. Treatment visualization
`IMPLEMENTED_BUT_PARTIAL` · Ghost, vectors, timeline play. · Viewer tests. · Collision, IPR, and attachment overlays. · C21, C22. · Plan. · StageViewer. · Play mode does not write the plan. · Frame time unmeasured. · Required. · `PRESENTATION_ONLY` except where it shows a stored mesh. · View state.

### K9. Predicted versus derived separation
`IMPLEMENTED_BUT_PARTIAL` · Code avoids calling interpolation a prediction of biology. There is no `PREDICTED` class in the enums yet. · Staging clinical-approval flag false. · Add `PREDICTED` only when a real predictive model exists. Until then, stages stay simulated. · B19. · Plan geometry. · Enum mapping. · No UI string says "predicted outcome" for lerp. · Not a hot path. · Required. · Interpolation is not a treatment forecast. · Class `SIMULATED`.

### K10. Truth-class vocabulary on derived meshes
`IMPLEMENTED_BUT_PARTIAL` · See B19 and H8. · Provenance tests. · Every file in K1–K8 carries a class. · B19. · Derived meshes. · Manifest. · A mesh without a class fails export. · Not a hot path. · Required. · Vocabulary does not upgrade truth. · Manifest field.

---

## L. Validation

### L1. GeometricValidationEngine authority
`IMPLEMENTED_AND_VERIFIED` · Intra-arch proximity, contact, and collision. Validation 2 wraps it and does not replace it. · `engines/validation/geometric_engine.py`, `test_geometric_validation_phase7.py`, `test_wp09_validation_2.py`. · Keep it the oracle for any faster checker. · Stage meshes. · trimesh. · A new checker must match report ids or a documented diff on the official case. · 214.5 s / 105.7 s cited. · Required. · Technical authority only. · Engine version on the report.

### L2. Collisions
`IMPLEMENTED_AND_VERIFIED` · Pair collisions on stage meshes, same arch. · Phase 7 tests, `test_p0_4_intra_arch_validation.py`. · Inter-arch collisions only after registration. Viewport highlight is C20. · L1, I16. · Stage meshes. · Current engine. · A penetrating fixture pair is detected. · Included in L1 cost. · Required. · Not a clinical collision grade. · Pair id.

### L3. Contacts
`IMPLEMENTED_BUT_PARTIAL` · Geometric contact findings exist. Clinical contacts do not. · Phase 7 tests, occlusion semantics. · Region output for F1. · L1. · Meshes and thresholds. · Current engine. · Contact does not get the clinical enum. · Included in L1. · Required. · `GEOMETRIC_CONTACT` or `CANDIDATE_CONTACT`. · Semantics field.

### L4. Proximity
`IMPLEMENTED_AND_VERIFIED` · Thresholded proximity. Official sample: 39 proximities, 0 collisions, status warning. · Phase 7 and WP-12 JSON. · Incremental updates. · L1. · Meshes. · Current engine. · Counts stable for a fixed threshold and mesh. · Dominant cost. · Required. · `COMPUTED`. · Threshold version.

### L5. Intersections
`IMPLEMENTED_BUT_PARTIAL` · Collision path covers mesh interference. Self-intersection of a single mesh is a MeshLib probe, not the validation report. · `test_wp10_production_cad.py`, tech benchmark. · One policy for self-intersection versus pair intersection. · L2, M12. · Meshes. · Geometric engine plus kernel probes. · A self-intersecting fixture is flagged by the chosen kernel. · MeshLib probe was 20 ms on one small crown. Full arches are unmeasured. · Required. · Flag is technical. · Kernel id.

### L6. Stage consistency
`IMPLEMENTED_AND_VERIFIED` · Final stage matches target in linear mode. Version binding exists. · Staging tests, `test_wp06_smart_staging.py`. · Consistency for non-linear modes. · J1. · Stages and target. · Stager check. · A broken final stage fails. · Cheap relative to collision. · Required. · Consistency is not clinical success. · Target version id.

### L7. Transform consistency
`IMPLEMENTED_AND_VERIFIED` · Tooth-frame transforms are deterministic and do not mutate source vertices. · `test_treatment_planning_phase5.py`, `test_stage_geometry_and_validation_keying.py`. · Same check after gizmo world-space edits are converted into the frame. · D3, C9. · Movements. · Planning engine. · Round-trip epsilon stated in the test. · Inside setup time. · Required. · Numeric consistency is not biological accuracy. · Transform hash.

### L8. Stale dependencies
`IMPLEMENTED_AND_VERIFIED` · Setup, staging, validation, and clinical tools have freshness enums. · WP-05, WP-06, WP-07, WP-09 tests. · Stale manufacturing outputs. · D12. · Version ids. · Existing freshness fields. · An edit sets downstream stale before the UI offers export as current. · Not a hot path. · Required. · Stale is `STALE`, not a quiet reuse. · Upstream version id.

### L9. Mesh validity
`IMPLEMENTED_BUT_PARTIAL` · Load and triangle-count gate. Watertight is informational. Manifold check fails on the sampled real crown. · `test_mesh_validation.py`, WP-10 benchmark. · A single validity report used by intake and by manufacturing, with different pass rules. · A6, M13. · Meshes. · trimesh plus adapter. · Open crowns can still be planned and cannot silently pass a watertight shell check. · Inspection was 13 ms on one small crown. · Required. · Validity is not printability. · Checker id.

### L10. Geometry validity of the plan
`IMPLEMENTED_BUT_PARTIAL` · Degenerate outputs are partly guarded by mesh construction rules. · `test_stage_geometry_and_validation_keying.py`. · Explicit checks for inverted faces and empty stage meshes. · L9. · Stage meshes. · trimesh. · An empty stage fails export. · Unmeasured. · Required. · Technical. · Check id.

### L11. IPR consistency
`IMPLEMENTED_BUT_PARTIAL` · Unavailable check rather than a false pass. · `test_wp09_validation_2.py`. · Real check in F12. · F12. · Sites and stages. · Validation 2. · See F12. · Unmeasured. · Required. · Not a prescription audit by a clinician. · Check id.

### L12. Attachment consistency
`IMPLEMENTED_BUT_PARTIAL` · Same honesty pattern as L11. · WP-09 tests. · Real check in G15. · G15. · Attachments. · Validation 2. · See G15. · Unmeasured. · Required. · Technical. · Check id.

### L13. Production geometry validity
`IMPLEMENTED_BUT_PARTIAL` · QC statuses exist. Shell, trimline, and undercut are not available. · `test_wp10_production_cad.py`, `wp10_real_case_evidence.json`. · QC of real shells. · M16. · Production meshes. · Production CAD engine. · A missing shell is `NOT_AVAILABLE`, not a pass. · Production CAD timing in one evidence file was 596 ms for the honesty layer, not for a shell. · Required. · QC is not manufacturing certification. · QC status.

### L14. Export integrity
`IMPLEMENTED_AND_VERIFIED` · Manifest SHA-256, verify detects mismatch. · `test_treatment_export_phase11.py`, `test_p0_3_export_integrity.py`. · Include future shell files under the same rule. · N8. · ZIP. · Export engine. · A flipped byte fails verify. · Export 34.7 s in the WP-10 evidence file. · Required. · Integrity is not clinical correctness. · Manifest hash.

### L15. Provenance integrity
`IMPLEMENTED_BUT_PARTIAL` · Hashes and provenance fields travel in JSON. There is no single chain check. · `test_fv01_provenance_guards.py`. · A verifier that rejects a package whose class or parent hash is missing. · B19, N10. · Manifest. · New check on export verify. · Fixture packages remain labeled fixture. · Not a hot path. · Required. · A complete chain is not human acceptance. · Chain version.

### L16. Independent verification
`IMPLEMENTED_BUT_PARTIAL` · `verify_package` recomputes hashes in-process. Process isolation exists for validation. · `test_wp12_performance.py` (report id match isolated vs in-process). · A second implementation or a fresh process that recomputes a stated subset of geometric checks. · L1, N10. · Package. · Isolated process pattern. · Independent check disagreement blocks "reverified." · Isolation was faster in the one cited sample (105.7 s vs 214.5 s) and is still slow. · Required. · Independent means a second computation, not a second opinion from a clinician. · Verifier version.

### L17. Clinical approval is not implied
`IMPLEMENTED_AND_VERIFIED` · Validation check state documents PASS as technical. Smart staging sets clinically approved false. UI truth mapping does not invent Verified from a fixture. · `domain/treatment_plan/validation_v2.py`, `truthState.ts`, feature-depth tests. · Keep the rule on every new PASS flag. · All validators. · Reports. · Existing copy and enums. · A regression test fails if a new panel says approved because validation passed. · Not a hot path. · Required on every build. · Human acceptance stays `REQUIRES_HUMAN_ACCEPTANCE`. · No implicit reviewer.

---

## M. Manufacturing CAD

### M1. Appliance shell generation
`NOT_IMPLEMENTED` · Boundary status `UNAVAILABLE`. No shell mesh is written. · `domain/treatment_plan/manufacturing.py`, `test_p5_validation_manufacturing_export.py`. · A shell per stage or a visible failure. · K3, M3. · Stage crowns. · Kernel from the FV-11 trial. · Shell volume is distinct from tooth volume. · No shell timing exists. · Required. · Shell is `DERIVED_GEOMETRY`, not an appliance approval. · Parameters and parent stage hash.

### M2. Tooth envelope
`NOT_IMPLEMENTED` · No envelope distinct from the stage tooth. · None. · A defined offset surface around the crown used by the shell. · M3. · Crown. · Same kernel trial. · Envelope contains the crown within a stated tolerance. · Unmeasured. · Required. · `DERIVED_GEOMETRY`. · Offset value.

### M3. Offsets
`IMPLEMENTED_BUT_PARTIAL` · MeshLib engineering offset produced 21,212 vertices from a 2,957-vertex crown in 154 ms. It is not a certified offset. · `wp10_tech_evaluation_benchmark.json`. · An offset that preserves clinical clearance intent and is validated. · M21. · Crown mesh. · meshlib behind the adapter, if the license clears and quality holds. · Offset distance checked on a sphere or cube oracle and on a real crown. · 154 ms per small crown is a lower bound, not a full-arch result. · Required. · Offset is `COMPUTED` engineering geometry. · Kernel version and distance.

### M4. Thickness
`NOT_IMPLEMENTED` · Status unavailable. · Manufacturing boundary tests. · A thickness field on the shell with a min/max report. · M1. · Shell. · Kernel plus a measurement. · A shell below the configured minimum fails QC. · Unmeasured. · Required. · Minimum is a manufacturing preference, not a material certification. · Thickness parameters.

### M5. Undercut analysis
`NOT_IMPLEMENTED` · Status not available in WP-10 evidence. · `wp10_real_case_evidence.json`. · Undercuts relative to a named insertion path. · M7. · Shell or model. · Kernel trial. · A constructed undercut is detected. · Unmeasured. · Required. · Analysis is `COMPUTED`. · Direction vector.

### M6. Blockout
`NOT_IMPLEMENTED` · No blockout mesh. · None. · A classified fill of undercuts for thermoform models, separate from the tooth. · M5. · Model. · Boolean or offset kernel. · Blockout is listed apart from the scan in the manifest. · Unmeasured. · Required for print models. · `DERIVED_GEOMETRY`. · Parameters.

### M7. Insertion path
`NOT_IMPLEMENTED` · No path object. · None. · A direction per arch or per stage, doctor-adjustable. · M5. · Doctor or a default labeled as such. · Viewport arrow. · Changing the path restales undercuts. · Not a hot path. · Required. · Direction is `PLANNED`. · Vector and author.

### M8. Trimline and cutline
`NOT_IMPLEMENTED` · Status unavailable. · Manufacturing boundary and WP-10 evidence. · A curve on the gingiva or a specified offset from the gingival margin, exported with the model. · A10 or a presentation policy that is explicit. · Margin or a doctor curve. · Curve on mesh. Public Maestro/ArchForm behavior is a product reference only. · Trimline length and closure are checked. · Unmeasured. · Required. · Curve is `PLANNED`. If gingiva is synthetic, the trimline says so. · Curve version and gingiva class.

### M9. Edge treatment
`NOT_IMPLEMENTED` · None. · None. · A defined rim or fillet after the trim, or an explicit omission. · M8. · Trimmed mesh. · Kernel trial. · Edge treatment parameters appear in the report. · Unmeasured. · Required if trim is in scope. · `DERIVED_GEOMETRY`. · Parameters.

### M10. Attachment relief
`NOT_IMPLEMENTED` · See G14. · None. · See G14. · G14, M1. · Shell and attachment. · Boolean kernel. · Relief depth matches the parameter within tolerance. · Unmeasured. · Required with attachments. · `DERIVED_GEOMETRY`. · G14 id.

### M11. Shell repair
`NOT_IMPLEMENTED` · No repair that outputs a shell. · Manifold `NotManifold` on a real crown shows repair is a prerequisite, not a polish. · A repair step with a before/after validity report. · M13, M21. · Open meshes. · Candidate kernels. Do not hide the Manifold failure. · Repaired solid passes the chosen validity test or the shell fails. · Unmeasured. · Required. · Repair is `DERIVED_GEOMETRY`. · Before and after hashes.

### M12. Self-intersection repair
`IMPLEMENTED_BUT_PARTIAL` · MeshLib reported 0 self-intersection pairs on one small crown. That is not a repair and not a full arch. · Tech benchmark JSON. · Detect on full arches and repair only with a measured method. · M11. · Meshes. · meshlib probe. · A fixture with a known intersection is detected. · 20 ms on one small crown. · Required. · Detection is `COMPUTED`. · Kernel id.

### M13. Watertightness
`IMPLEMENTED_BUT_PARTIAL` · trimesh reports the sampled crown not watertight. Manifold rejects it. Planning is still allowed. · Tech benchmark, mesh validation tests. · Watertight requirement for shells and print models only. · M1, L9. · Output meshes. · trimesh and manifold. · A shell export fails if not watertight. · Inspection is cheap per small mesh. Full shells unknown. · Required for printables. · A watertight flag is `COMPUTED`. · Checker id.

### M14. Mesh cleanup
`NOT_IMPLEMENTED` · See A11 for scans. No cleanup for shells. · None. · Degenerate-face removal with a diff report. · M11. · Shells. · Kernel. · Cleanup does not change clinical tooth vertices unless asked. · Unmeasured. · Required. · Cleanup is a child mesh. · Parameter record.

### M15. Manufacturing tolerances
`NOT_IMPLEMENTED` · No tolerance profile. · None. · Configurable minima for thickness, clearance, and offset, labeled as preferences. · E13, M4. · Doctor or lab preferences. · QC. · QC reads the profile version. · Not a hot path. · Required. · Tolerances are not a certified process. · Profile id.

### M16. Manufacturing QC
`IMPLEMENTED_BUT_PARTIAL` · Status enum can say not available or requires review. It does not certify. · `test_wp10_production_cad.py`. · A report of the checks that actually ran. · M4, M5, M13. · Shells. · Production CAD engine. · Empty checks cannot be an overall pass. · Honesty-layer timing is not QC timing. · Required. · QC PASS is technical. · Report hash.

### M17. Printable and exportable meshes
`NOT_IMPLEMENTED` · Stage STLs export. They are treatment meshes. Printable preparation is `BOUNDARY_ONLY` when stages exist. · `build_manufacturing_boundary_report`. · A print mesh that passed M16. · M1, N2. · Shell or model. · Export engine. · The print file name cannot match the raw scan name. · Unmeasured. · Required. · `DERIVED_GEOMETRY`. · QC report id.

### M18. Stage packages
`IMPLEMENTED_BUT_PARTIAL` · ZIP contains stage treatment meshes and JSON. · Export tests. · One folder per stage with tooth, attachment, shell, and QC. · N1, M17. · Stage outputs. · Export engine. · Missing shell is an explicit file-level status, not an omitted surprise. · See export timing. · Required. · Package kind is named. · Manifest.

### M19. Manufacturing reports
`NOT_IMPLEMENTED` · Notes say QC is unavailable. · WP-10 evidence. · A report a lab can read, with limitations. · M16, N6. · QC results. · Export. · Report numbers match QC JSON. · Not a hot path. · Required. · Report is not a device certificate. · Report hash.

### M20. Independent export verification of manufacturing files
`NOT_IMPLEMENTED` · Hash verify exists for the current ZIP contents. It has no shell files to check. · Export verify tests. · Extend verify to shells and QC. · L16, N10. · Package. · Verifier. · A truncated shell fails verify. · Unmeasured. · Required. · Verify is integrity. · Verifier version.

### M21. Geometry kernels as inspection tools
`IMPLEMENTED_BUT_PARTIAL` · Adapter exposes trimesh inspection, Manifold validity and booleans, MeshLib offset and self-intersection. · `engines/geometry/production_geometry/`, `test_wp10_production_cad.py`, tech benchmark. · A written kernel choice after the crown repair trial. Licenses flagged in the master plan. · FV-11. · Real crowns and a solid oracle. · The three backends. Keep the adapter. · A kernel that fails the crown stays available as a negative result, not as the default shell builder. · See M3, M12, M13 numbers. · Required before any kernel is the default. · Kernel output is `COMPUTED` or `DERIVED_GEOMETRY`. · Backend name and version on every result.

---

## N. Production and export

### N1. Production package
`IMPLEMENTED_BUT_PARTIAL` · Engineering treatment ZIP, package kind `engineering_treatment_export`. · `engines/export/treatment_export.py`. · A production package kind that can contain shells or an explicit omission list. · M18. · Plan outputs. · Export engine. · Kind is in the manifest. · 34.7 s cited for one export path. · Required. · Package is not a released appliance. · Package kind and hash.

### N2. Per-stage outputs
`IMPLEMENTED_BUT_PARTIAL` · Stage meshes and JSON. · Export tests. · Add shell, trimline, and attachment files per stage when they exist. · J21, M17. · Stages. · Export engine. · Stage count in the manifest equals the plan. · Included in export time. · Required. · File class per entry. · Stage id in the name.

### N3. Naming
`IMPLEMENTED_BUT_PARTIAL` · Deterministic internal names. · Export ordering tests. · Human-readable names that include case, arch, stage, and role, without implying certification. · N2. · Manifest. · Export engine. · Names are stable across verify. · Not a hot path. · Required. · Names are labels. · Naming rule version.

### N4. Metadata
`IMPLEMENTED_BUT_PARTIAL` · JSON payloads for plan, staging, validation, proposals. · Export tests. · Metadata for kernels, preferences, and truth classes. · B19. · Domain objects. · Existing JSON. · A missing required metadata key fails the package build. · Serialize was 6.6 s and 16.6 MB for a review bundle in WP-12. · Required. · Metadata is not a clinical letter. · Schema version.

### N5. Provenance in the export
`IMPLEMENTED_BUT_PARTIAL` · Provenance fields and hashes. · `test_p0_3_export_integrity.py`. · Full chain from master plan section 5.2. · L15. · Objects. · Manifest. · Fixture exports say fixture. · Not a hot path. · Required. · Export does not upgrade class to `VERIFIED`. · Chain.

### N6. Reports
`IMPLEMENTED_BUT_PARTIAL` · Machine JSON, not a doctor/lab report. · Export and validation summary tests. · One readable report for validation limits and one for manufacturing limits. · F9, M19. · Results. · Template over JSON. · Report is regenerated from the same hashes. · Not a hot path. · Required. · Narrative cannot contradict JSON. · Report hash.

### N7. Validation package
`IMPLEMENTED_AND_VERIFIED` · Validation JSON is inside the engineering export. · Export and WP-09 tests. · Include the independent verifier output. · L1, L16. · Reports. · Export engine. · Report id in the package matches the session. · Included in export time. · Required. · Package PASS is technical. · Report id.

### N8. Export verification
`IMPLEMENTED_AND_VERIFIED` · `verify_package` recomputes hashes. · `test_p0_3_export_integrity.py`. · Cover new file types. · L14. · ZIP. · Export engine. · Tamper test stays in CI. · Unmeasured separately from export. · Required. · Verify is not approval. · Result and time.

### N9. Reopen
`IMPLEMENTED_BUT_PARTIAL` · `reopen_for_audit` reads the ZIP and does not restore an editable session. Browser reopen uses session storage and the API. · Export tests, `p8Workflow.test.tsx`. · Reopen into a case that can be reverified and, when possible, edited. · A13, N8. · ZIP or local case. · Both paths, documented as different until unified. · Audit reopen agrees with verify. Session reopen agrees with the stored case id. · Not a hot path. · Required. · Reopen is not a new prescription. · Source of the reopen: zip versus session.

### N10. Reverify
`IMPLEMENTED_BUT_PARTIAL` · Hash verify is the reverify we have. · Same as N8. · Recompute a geometric subset in a clean process (L16). · L16, N9. · Package. · Isolated process. · Mismatch is a hard failure. · See L16. · Required. · Reverify is integrity plus a stated geometric subset. · Verifier log.

### N11. Deterministic hashes
`IMPLEMENTED_AND_VERIFIED` · SHA-256 per file and manifest. · Export tests. · Hash the new manufacturing files the same way. · N8. · Bytes. · Existing hasher. · Two exports of an unchanged plan match. · Included in export. · Required. · Hash equality is not clinical equality. · Algorithm SHA-256.

### N12. Failure-safe export
`IMPLEMENTED_BUT_PARTIAL` · Incomplete bundles can be refused. Failure injection exists for tests. · `test_wp13_reliability.py`, export tests. · A failed export does not replace the last good ZIP. · O13. · Filesystem. · Export engine. · Injected failure leaves the previous package hash unchanged. · Not a hot path. · Required. · Failure is visible. · Previous package id.

### N13. No silent substitution
`IMPLEMENTED_AND_VERIFIED` · Real uploads refuse the fixture backend. Fixture mode requires a hash match. Export uses `tooth_ref` when FDI is absent rather than inventing numbers. · `test_wp01_real_clinical_pipeline.py`, `test_p0_3_export_integrity.py`. · The same rule for shells: no substitution of the tooth mesh. · M1, processing modes. · Uploads and exports. · Existing gates. · A regression that substitutes fixture segmentation fails CI. · Not a hot path. · Required. · Substitution ban is a product rule. · Backend name on the job.

---

## O. Reliability and recovery

### O1. Processing states
`IMPLEMENTED_AND_VERIFIED` · Job states include running, failed, cancelled, interrupted, stale, with heartbeat. · `test_fv01_processing_lifecycle.py`, `processing.py`. · The same state machine for manufacturing jobs. · FV-13. · Jobs. · Existing processor. · UI labels match API states. · Heartbeat is cheap. · Required. · State is operational, not clinical. · Job id.

### O2. Interruption
`IMPLEMENTED_AND_VERIFIED` · Interrupted jobs persist and do not become success. · `test_wp13_reliability.py`, `test_wave1_real_segmentation_recovery.py`. · Interrupt during validation and shell jobs. · O1. · Running job. · Failure-injection hooks. · Interrupted segmentation is not reusable as complete. · Not a hot path. · Required. · Partial output is labeled partial. · Job state.

### O3. Cancellation
`IMPLEMENTED_AND_VERIFIED` · Cancel endpoint demotes in-flight segmentation. · WP-13 and lifecycle tests. · Cancel of validation and export. · O1. · Job id. · API. · Cancel does not record a fake duration (remaining-time tests). · Not a hot path. · Required. · Cancel is not a clinical reject. · Job state.

### O4. Restart
`IMPLEMENTED_BUT_PARTIAL` · Case JSON and session pickle reload. · `test_p7_performance_reliability.py`. · Restart across a code change without pickle breakage. · A13. · Disk. · Store. · A restarted API serves the same case id. · Session compose cached 5.33 s after a cold 104.7 s. · Required. · Restart does not re-approve a plan. · Schema version.

### O5. Stale jobs
`IMPLEMENTED_AND_VERIFIED` · Heartbeat timeout marks stale. · `test_fv01_processing_lifecycle.py`. · Stale policy for long validations so a 100 s job is not marked stale by a short timeout. · O1, J17. · Heartbeat. · Existing detector. · A live long job stays running. A dead job becomes stale. · Timeout must be longer than the known validation duration or the job must heartbeat during it. · Required. · Stale is operational. · Timestamps.

### O6. Duplicate jobs
`IMPLEMENTED_AND_VERIFIED` · Same input hash does not start a conflicting duplicate. · `test_p7_performance_reliability.py`. · Same rule for export and manufacturing. · O1. · Input hash. · Processor. · Two clicks yield one job. · Not a hot path. · Required. · Dedup is not a data-quality judgment. · Job id.

### O7. Browser refresh
`IMPLEMENTED_AND_VERIFIED` · sessionStorage case and workspace; API rehydrate. · `caseWorkspacePersistence.test.ts`, `p8Workflow.test.tsx`. · Refresh during a running job shows the live status, not a completed fake. · C23, O1. · Browser and API. · Existing mount path. · A test covers refresh mid-processing. · Not a hot path. · Required. · Refresh does not apply an edit. · Case id.

### O8. Backend restart
`IMPLEMENTED_BUT_PARTIAL` · See O4. Worker death can surface as failure. · `test_api_cases.py` worker-exit case. · Documented recovery steps and a durable session schema. · O4. · Disk. · Store. · In-flight job becomes interrupted or stale, not success. · Unmeasured. · Required. · Restart is operational. · Job state.

### O9. Crash recovery
`IMPLEMENTED_BUT_PARTIAL` · Interruption and atomic case persistence cover API crashes incompletely. No desktop crash reporter. · WP-13 tests. · Recover the last committed version after a killed process. · O10, FV-DESK. · Disk. · Store. · Uncommitted export temps are discarded. · Not a hot path. · Required. · Recovery does not invent the lost edit. · Last committed version id.

### O10. Atomic persistence
`IMPLEMENTED_AND_VERIFIED` · Case store writes are atomic enough to be tested against interruption. · `test_wp13_reliability.py`. · The same pattern for session schema and export. · A13. · Files. · Store. · A crash mid-write does not leave a truncated JSON as current. · Not a hot path. · Required. · Atomicity is not backup. · Write protocol.

### O11. Partial-result preservation
`IMPLEMENTED_BUT_PARTIAL` · Completed arches can persist while a job fails if the implementation path says so. Cancel demotes them. · Wave 1 and WP-13 tests. · A clear rule: which partial segmentations remain usable. · O2, B1. · Segmentation store. · Segmentation store. · A partial result cannot generate a full plan. · Not a hot path. · Required. · Partial is `REQUIRES_REVIEW`. · Per-arch status.

### O12. Version recovery
`IMPLEMENTED_BUT_PARTIAL` · Setup versions can be restored while the process has them. · WP-05 tests. · Restore after API restart from the durable schema. · D12, O4. · Versions. · Version store. · Restored version hash matches. · Not a hot path. · Required. · Restore is not a new approval. · Version id.

### O13. Export recovery
`IMPLEMENTED_BUT_PARTIAL` · A finished ZIP remains after session reload in the reliability tests. · `test_wp13_reliability.py`. · Failed replacement does not delete it (N12). · N12. · Files. · Export engine. · The last good hash is listed after a failed second export. · Not a hot path. · Required. · Old package is not "more approved." · Package id.

### O14. Failed import recovery
`IMPLEMENTED_BUT_PARTIAL` · Invalid meshes fail validation and the case remains. · `test_mesh_validation.py`, API tests. · The doctor can remove the bad arch and upload again without a stuck processing state. · A6, O1. · Uploads. · Case API. · A failed STL does not block the other arch's file from being deleted and replaced. · Not a hot path. · Required. · Import failure is not a patient-data judgment. · Asset status.

---

## P. Professional UX

### P1. Case intake UX
`IMPLEMENTED_AND_VERIFIED` · `CaseIntakePanel` uploads through the API. Generate stays disabled until the gates pass. · `caseIntake.test.ts`, App tests with mocked API. · PLY and orientation controls when those exist. · A1. · User files. · Existing panel. · The panel lists filename, size, and validation. · Not a hot path. · Required. · The panel does not say the scan is clinically acceptable. · Asset status.

### P2. Analysis UX
`IMPLEMENTED_AND_VERIFIED` · Analysis shows intelligence and limitations. · `wp02DentalIntelligence.test.ts`, analysis presentation tests. · Tooth-level unresolved identity. · B5, B19. · Intelligence payload. · Analysis panel. · Unavailable fields are visible. · Not a hot path. · Required. · Analysis is not a diagnosis. · Truth states.

### P3. Segmentation review UX
`IMPLEMENTED_BUT_PARTIAL` · Read-only review of pipeline state. · Wave 3 spec is mocked. · Edit tools from B4. · B4, B5. · Segmentation. · Analysis workspace. · A correction is confirmed in the UI and in the API. · Unmeasured. · Required. · The screen says review, not verified accuracy. · Segmentation version.

### P4. Setup UX
`IMPLEMENTED_AND_VERIFIED` · Setup panel, versions, viewport edits. · `wp05TreatmentSetup.test.ts`. · Arch-form and group tools. · D2, C9. · Plan. · Existing panels. · The current version id is visible. · Unmeasured. · Required. · Setup UI does not say optimal. · Version id.

### P5. Staging UX
`IMPLEMENTED_BUT_PARTIAL` · Regenerate, version, timeline. · Staging panel and timeline tests. · Table, compare, rate controls. · J18, J20. · Stages. · Existing panel. · Stale staging is labeled before regenerate. · Unmeasured. · Required. · UI does not say clinically optimal. · Freshness.

### P6. Refinement UX
`IMPLEMENTED_AND_VERIFIED` · Gizmo plus inspector, IPR/attachment status pointers. · Refinement panel, toolbar tests. · Geometry edits for IPR and attachments. · C9, F6, G10. · Selection. · Existing workspace. · Refinement and setup do not both own commit. · Unmeasured. · Required. · Refinement is doctor editing. · Action ownership map.

### P7. Validation UX
`IMPLEMENTED_AND_VERIFIED` · Findings, counts, unavailable checks. · `ValidationPanel.test.tsx`, feature-depth tests. · Viewport highlights. · C20, L1. · Report. · Validation panels. · A technical pass is worded as technical. · Not a hot path. · Required. · No approval language. · Report id.

### P8. Production UX
`IMPLEMENTED_BUT_PARTIAL` · Production panel explains unavailable manufacturing and can request export. · Production panel tests, feature-depth tests. · Shell preview and QC when M16 exists. · M16, N1. · Production payload. · Existing panel. · Unavailable shell is the headline until a shell exists. · Not a hot path. · Required. · No certification badge. · Production truth state.

### P9. Contextual toolbar
`IMPLEMENTED_AND_VERIFIED` · `resolveToolbar` by workspace and selection. · `wave6Toolbar.test.tsx`. · New tools register here instead of a second bar. · C24. · Context. · `toolbar.ts`. · A blocked tool says why. · Not a hot path. · Required. · Toolbar does not invent a command the API rejects. · Command id.

### P10. Adaptive inspector
`IMPLEMENTED_AND_VERIFIED` · Modes for empty, tooth, group, processing, failure, and each workspace. · `wave10AdaptiveInspector.test.tsx`. · Modes for attachment, IPR site, and shell. · P6. · Selection and truth model. · `buildInspectorModel`. · One inspector, no page scroll. · A wave 10 test includes a performance assertion on model build. · Required. · Inspector does not upgrade truth. · Mode id.

### P11. Command ownership
`IMPLEMENTED_AND_VERIFIED` · `actionOwnership.ts` maps header, form, toolbar, tooth toolbar, inspector. · Wave 10 tests. · Every new command gets an owner. · P9, P10. · Ownership table. · Existing map. · A command without an owner fails the test. · Not a hot path. · Required. · Ownership is UX structure. · Map version.

### P12. No duplicate controls
`IMPLEMENTED_AND_VERIFIED` · Built-in camera tools are off because the toolbar owns them. Commit is inspector-owned. · `showBuiltinCameraTools={false}`, ownership tests. · Keep the rule for new panels. · P11. · UI. · App wiring. · Duplicated commit buttons fail a test. · Not a hot path. · Required. · One owner. · Ownership map.

### P13. No-scroll workspace
`IMPLEMENTED_AND_VERIFIED` · `html` and the workspace overflow hidden. Panels scroll inside. Inspector column does not scroll the page. · `global.css`, `layoutBudget()`. · Re-check when the tooth table arrives. · P20. · CSS. · Existing shell. · A layout test or a short browser check at the three existing viewports. · Not a hot path. · Required. · Scroll policy is not accessibility completion. · CSS rule.

### P14. Keyboard and mouse UX
`IMPLEMENTED_AND_VERIFIED` · See C24. · Shortcut tests. · Discoverable shortcut help. · C24. · Keyboard map. · Existing matcher. · Focused input does not steal single-key view shortcuts. · Not a hot path. · Required. · Shortcuts are not the only path. · Map.

### P15. Information hierarchy
`IMPLEMENTED_BUT_PARTIAL` · Primary status, step form, viewport, inspector. · Smart UX tests. · The viewport stays primary when reports grow. · P26. · Layout. · Clinical chrome. · A critical failure is visible without opening an advanced section. · Not a hot path. · Required. · Hierarchy does not hide limitations. · Layout budget.

### P16. Truth-state communication
`IMPLEMENTED_AND_VERIFIED` · Labels for not available, requires review, fixture, blocked, failed. The mapper does not invent Verified. · `truthState.ts`, `FixtureBadge.test.tsx`, feature-depth tests. · Extend labels to the unified class list without a second slang vocabulary. · B19. · Truth fields. · Design-system mapper. · Fixture data cannot render as verified. · Not a hot path. · Required. · Wording is part of the product contract. · Mapper version.

### P17. Failure and recovery UX
`IMPLEMENTED_AND_VERIFIED` · Failed, cancelled, interrupted, stale, and unavailable inspector modes. · Wave 10 spec (mocked states), processing presentation tests. · Recovery actions that match O2–O4. · O1. · Job status. · Existing modes. · Each state has a next action that does not claim success. · Not a hot path. · Required. · Failure copy is operational. · State.

### P18. Contextual actions
`IMPLEMENTED_AND_VERIFIED` · Next-action resolver and blocked steps that explain rather than navigate. · `workflowWave7.test.ts`. · Actions for new objects (attachment, shell). · P9. · Workflow evidence. · `nextAction.ts`. · A blocked step does not fire the job. · Not a hot path. · Required. · The next action is not clinical advice. · Action id.

### P19. Stage timeline UX
`IMPLEMENTED_BUT_NOT_WORLD_CLASS` · See C22 and J18. · Timeline tests. · Markers for IPR and attachments. · J18. · Stages. · Timeline component. · Play stops at the last stage. · Unmeasured. · Required. · Play is simulation. · Stage index.

### P20. Tooth table
`NOT_IMPLEMENTED` · A dental arch map exists. It is not a numeric table. · Inspector and map tests. · A table of movement components per selected tooth, bound to D3. · D3, J20. · Movements. · New view. · Table edits and inspector edits write the same transaction. · Virtualize. · Required. · Cells show frame and truth. · Tooth ref.

### P21. Clinical review workspace
`IMPLEMENTED_BUT_PARTIAL` · The seven steps are a review shell. They are not a dense clinical review layout with compare and tables. · Workflow tests. · A review layout that can show current, target, collisions, and limitations together. · P15, C19, C20. · Plan and validation. · Existing shell. · Limitations remain on screen in that layout. · Unmeasured. · Required. · Review layout is not approval. · Step id.

### P22. Visual density
`IMPLEMENTED_BUT_PARTIAL` · CAD tokens and compact chrome exist. Density has not been reviewed against a full clinical table. · Design-system tests. · A density pass after tables exist, with no second theme experiment mixed in. · P20. · UI. · CSS tokens. · Primary actions remain findable at 1366×768. · Not a hot path. · Required at the end of FV-UX. · Density does not remove truth labels. · Screenshot only if a measurement cannot describe the issue.

### P23. Dark and light strategy
`IMPLEMENTED_BUT_PARTIAL` · Dark tokens only. · `tokens.css`. · A documented decision. Add light only if contrast or clinic environments require it. · P22. · CSS. · Existing tokens. · If a second theme exists, truth colors still meet contrast. · Not a hot path. · Decision required. Theme itself is not clinical. · Theme id.

### P24. Accessibility
`IMPLEMENTED_BUT_PARTIAL` · Many controls have names and live regions. No systematic suite. · Component tests cover some roles. · Keyboard path for every owner-command, focus return, and contrast of truth colors. · P14. · UI. · Existing semantics. · An automated a11y check on the seven steps. · Not a hot path. · Required. · Accessibility does not replace truth labels. · Check version.

### P25. Focus management
`IMPLEMENTED_BUT_PARTIAL` · Dialogs and panels use some focus behavior. It is not specified for gizmo versus panel. · Partial component coverage. · Focus returns to the invoker. Viewport shortcuts respect focused fields (P14). · P14. · DOM. · UI code. · A modal trap test for export failure. · Not a hot path. · Required. · Focus is UX state. · Not clinical.

### P26. Viewport remains primary
`IMPLEMENTED_AND_VERIFIED` · The workspace is built around the canvas. · CSS and App layout. · New tables dock beside it and do not replace it. · P13, P21. · Layout. · Shell. · At the target viewports the canvas remains visible without page scroll. · Not a hot path. · Required. · The viewport shows classified geometry. · Layout.

---

## Q. Models and adapters

### Q1. Adapter architecture
`IMPLEMENTED_BUT_PARTIAL` · Segmentation and research adapters fail closed. Contracts exist for ONNX. · `test_segmentation_configuration_phase13.py`, `test_p6_advanced_planning_intelligence.py`. · The same contract shape for every new model family. · FV-MODEL. · None until a model is configured. · `adapters/`. · An unconfigured model cannot be selected by default. · Not a hot path. · Required. · Adapter output is `PROPOSED` or `SEGMENTED` with review. · Contract version and artifact hash.

### Q2. Segmentation model
`IMPLEMENTED_BUT_NOT_PROVEN` + `ENVIRONMENT_BLOCKED` · Same path as B1. Tensor shapes were re-derived from `instseg_full.ckpt`. Class names were not. Inference did not run. Recommendation B: keep ToothInstanceNet as the primary path and require the GPU runtime package. It is not production-ready here. · `docs/FV01_SEGMENTATION_EXECUTION_BENCHMARK.md`. · Execute on a CUDA machine with pointops. · B1. · Real scans plus the pinned checkpoint. · ToothInstanceNet. · See B1. · Runner about 328 ms. No inference sample. · Required. · Clinical accuracy `NOT_ESTABLISHED`. · Pinned SHA-256 `100c68a9b120402cc75539eff6347bd998bce8b1d4f01550638f471797d70803`.

### Q3. Tooth identity model
`NOT_IMPLEMENTED` · Seven-class map is not an identity model. · Manifest claims. · A model or a doctor workflow, compared on real cases. · B3. · Cases with a key. · None selected. · It must beat "leave unresolved" without increasing false FDI. · Unmeasured. · Required before automatic FDI. · `PROPOSED` until reviewed. · Model hash.

### Q4. Landmark model
`REQUIRES_EXTERNAL_TECHNOLOGY` · `landmarks_full.ckpt` is inventoried and not wired to the official artifact. Product landmarks are extrema. · Benchmark inventory, B9. · A trial against doctor points. · B9. · Real crowns plus a key. · That checkpoint only after license and accuracy review. · Extrema remain the fallback and stay labeled. · Unmeasured. · Required before automatic landmarks. · `PROPOSED`. · Checkpoint hash.

### Q5. Orientation model
`NOT_IMPLEMENTED` · See A5. · None. · Optional proposal, doctor accepts. · A5. · Scans. · Slicer ASO is a reference. · Rejection leaves the scan untransformed. · Unmeasured. · Optional. · `PROPOSED`. · Model hash.

### Q6. Registration model
`NOT_IMPLEMENTED` · See I3. · None. · Deterministic ICP before any learned registration. · I5. · Mesh pairs. · Open3D candidate. · Learned methods stay challengers. · Unmeasured. · Required only if ICP is insufficient on the bite cases. · `PROPOSED` if learned. · Model or algorithm id.

### Q7. Treatment proposal model
`REQUIRES_EXTERNAL_TECHNOLOGY` · See E14. · Evaluations not run. · A real-case comparison against the deterministic planner. · E14. · Real plans. · STTAlign/TADPM remain unavailable. · Validation gate stays mandatory. · Unmeasured. · Not required for First Version if deterministic planning is honest. · `PROPOSED`. · Model hash.

### Q8. Staging proposal model
`NOT_IMPLEMENTED` · Staging is deterministic lerp. · Staging tests. · A proposal model only as a challenger to the constraint stager. · J2, E14. · Plans. · None. · Linear and rate-based stagers remain available. · Unmeasured. · Not required for the gate. · `PROPOSED`. · Model hash.

### Q9. Attachment proposal model
`NOT_IMPLEMENTED` · Rule stub is "nonzero movement." · Proposal tests. · Rules before models. · G8. · Movements. · Preference rules. · A model cannot place a solid the doctor did not accept. · Unmeasured. · Rules are enough for the gate. · `PROPOSED`. · Rule or model id.

### Q10. IPR proposal model
`NOT_IMPLEMENTED` · Centroid heuristic. · F5. · Geometry first. A model is a challenger. · F5. · Contact regions. · Geometric engine. · Model amounts that disagree with the measurement stay proposals. · Unmeasured. · Measurement is the gate. · `PROPOSED`. · Method id.

### Q11. Anatomy reconstruction model
`NOT_IMPLEMENTED` · No reconstructor. · None. · Only with a measured error on held-out real surfaces. · B18. · Incomplete scans. · None selected. · Output class `RECONSTRUCTED`. · Unmeasured. · Not required for complete crowns. · `RECONSTRUCTED`. · Model hash.

### Q12. Propose, record, validate, doctor decides
`IMPLEMENTED_BUT_PARTIAL` · The loop exists for deterministic setup alternatives and for IPR/attachment status. It does not exist for models that cannot run. · P6 tests, proposal tests. · Every new proposal type joins the loop. · E15, D14. · Proposals. · Validation engine and edit history. · No API writes a model output straight onto the current plan. · Uses L1. · Required. · The doctor decision is the only human acceptance. · The four-step record.

---

## R. Performance

### R1. CPU path
`IMPLEMENTED_BUT_NOT_WORLD_CLASS` · API and validation run on CPU. Isolation helped one workload. · WP-12 JSON. · Keep a CPU path for every shipping feature. · FV-PERF. · Official case. · Current Python stack. · CPU path results match the reference. · 105.7 s isolated upper validation is the published mark to beat with a correctness check. · Required. · Faster CPU code is still technical. · Benchmark file.

### R2. GPU
`ENVIRONMENT_BLOCKED` · Segmentation benchmarks record no NVIDIA driver on this host. The Kaggle artifact used a T4-class GPU. · `research/benchmark/*/benchmark.json`. · A GPU run and a CPU fallback for FV-01. · B1. · CUDA machine. · ToothInstanceNet runtime. · CPU fallback is explicit when the GPU is missing. · Unmeasured here. · Required for the inference claim. · GPU use is not accuracy. · Device string in the log.

### R3. WebGL
`IMPLEMENTED_BUT_NOT_PROVEN` · Three.js WebGL viewport. · StageViewer. No stored frame-time budget. · Baseline on the official scene. · C25. · Real meshes. · Three.js. · Interaction baseline stored before a renderer change. · Unmeasured. · Required. · Frame time is not clinical quality. · GPU and browser in the note.

### R4. WebGPU
`NOT_IMPLEMENTED` · No product path. · Docs may mention it; code does not. · Trial only if R3 misses the budget. · R3. · Same scene. · A prototype outside the default until it wins. · Picking results match WebGL. · Comparison required. · Not required until R3 fails. · A faster frame is still the same geometry. · Trial note.

### R5. WASM
`NOT_IMPLEMENTED` · No product WASM. · None. · Trial for a measured hot loop only. · R1. · That loop. · Unknown. · Results match the Python or JS oracle. · Comparison required. · Not required by default. · Same outputs. · Module hash.

### R6. Workers
`IMPLEMENTED_BUT_PARTIAL` · Server threads and a validation process pool. Client `geometryWorkers.ts` validates a request shape and does not run a pool. · `test_wp12_performance.py`, worker stub. · A real client worker only after a main-thread baseline says it is needed. · R3. · Meshes. · Existing server pool. · Worker and main thread return the same buffer hash. · Server isolation is the measured one. · Required for long validation. · Cancellation still works. · Worker protocol version.

### R7. Transferable buffers
`NOT_IMPLEMENTED` · Buffers are built on the main thread. · StageViewer. · Use only with R6. · R6. · Mesh arrays. · PostMessage transfers. · No detached-buffer bug in a test. · Unmeasured. · Optional. · Transfer does not change vertices. · Test id.

### R8. Caching
`IMPLEMENTED_AND_VERIFIED` · Validation report cache and a large compose-time drop when cached (104.7 s to 5.33 s). · `test_wp12_performance.py`, WP-12 JSON. · Cache keys must include every parameter that changes geometry. · L8. · Reports. · `report_cache.py`. · A threshold change misses the cache. · Cited numbers. · Required. · A cache hit is not a new computation claim. · Cache key fields.

### R9. BVH
`IMPLEMENTED_AND_VERIFIED` · three-mesh-bvh for picking. Visibility toggles aim not to rebuild it. · Workspace and WP-12 client tests. · Rebuild policy when vertices move. · C5. · Tooth meshes. · three-mesh-bvh. · Moved teeth still pick correctly. · Micro tests exist. Full-scene cost unmeasured. · Required. · BVH is an acceleration, not a clinical structure. · Library version.

### R10. Mesh decimation
`NOT_IMPLEMENTED` · Full resolution is shown and validated. · None. · Display LOD only, with a test that export uses the full mesh. · R3, N2. · Crowns. · A decimator chosen by trial. · Hausdorff distance of the display mesh is recorded and excluded from validation. · Comparison required. · Optional. · Display mesh is `PRESENTATION_ONLY`. · LOD parameters.

### R11. Progressive loading
`NOT_IMPLEMENTED` · The viewer waits for full buffers. · StageViewer effect. · Show the arch before secondary overlays. · R3. · Case payload. · Client loader. · A cancelled load leaves no half-labeled tooth. · Unmeasured. · Required if load is visibly blocking on the official case. · Partial display is presentation. · Load id.

### R12. Incremental scene updates
`IMPLEMENTED_BUT_PARTIAL` · Some visibility paths avoid a full BVH rebuild. Tooth motion still needs a measured update path. · `wp12Performance.test.ts`. · Update one tooth's matrix or vertices without rebuilding the arch. · C9, R9. · One tooth. · Three.js. · A single-tooth edit does not allocate a full arch copy, or the allocation is documented and accepted. · Unmeasured. · Required for gizmo use. · Incremental display matches the stored mesh. · Update path id.

### R13. Geometry kernel acceleration
`IMPLEMENTED_BUT_NOT_PROVEN` · Kernel probes are fast on one small crown and do not accelerate validation. · Tech benchmark. · Accelerate only the operation that the baseline says is hot, with a correctness diff. · M21, L1. · Official case. · Existing kernels. · Results match the unaccelerated oracle. · See M3 and L1. · Required before a kernel replaces trimesh validation. · Speed is not a new truth class. · Before/after note.

### R14. Background processing
`IMPLEMENTED_AND_VERIFIED` · Processing jobs run off the request thread. · Lifecycle tests. · Validation and shells use the same pattern so the UI can poll. · O1, J17. · Jobs. · `processing.py`. · The UI remains usable while a job runs. · Long jobs are the point. · Required. · Background is not silent success. · Job id.

### R15. Cancellation of heavy work
`IMPLEMENTED_BUT_PARTIAL` · Processing cancel works. A 200 s validation cancel is not the tested path. · Lifecycle tests versus WP-12 durations. · Cancel validation and shell jobs within a stated latency. · O3, R14. · Those jobs. · Job control. · Cancelled work does not publish a report. · Must be measured. · Required. · Cancel is operational. · Job state.

### R16. Memory lifecycle
`IMPLEMENTED_BUT_NOT_PROVEN` · No stored memory profile. Review JSON was 16.6 MB, which is not the mesh peak. · WP-12 JSON. · Peak RSS for plan, validate, and view on the official case. · FV-PERF. · Official case. · Process metrics. · A leak test across ten stage scrubs. · Unmeasured. · Required. · Memory is a budget, not a clinical limit. · RSS note.

### R17. Large scans
`NOT_IMPLEMENTED` · No decimation, streaming, or density policy. The official crowns are modest. · One tooth at 2,957 vertices in the kernel probe. Arch loads are larger (manifest instance arrays on the order of 70k labels). · A defined upper density and a behavior when exceeded. · R10, A6. · A denser second or third scan. · Measure first. · Over-density fails with a reason or enters a reviewed display LOD. · Unmeasured. · A denser-than-official scan is required before claiming large-scan support. · Density handling is technical. · Vertex counts in the log.

---

## S. Desktop delivery

### S1. Installable application
`NOT_IMPLEMENTED` · `package.json` starts Vite. No installer. · No desktop project file. · FV-DESK trial, then an installer. · S7. · Clean machine. · Undecided shell. · Install, run, and uninstall without Node tooling knowledge. · Unmeasured. · Required for the final gate. · Install is not regulatory clearance. · Version of the installer.

### S2. Windows, macOS, and Linux
`NOT_IMPLEMENTED` · Development is on Linux. No packaged targets. · This audit host is Linux. · One trial per OS or a written, evidence-based cut if an OS cannot host the GPU stack. · S1. · Hardware. · Undecided. · The gate case opens on each claimed OS. · Unmeasured. · Required for each OS that is claimed. · OS support is not clinical validation. · OS matrix.

### S3. Local backend
`IMPLEMENTED_BUT_PARTIAL` · FastAPI runs locally in a venv the developer starts. · README and API tests. · The installer starts and stops it. · S1. · Local port. · Current API. · The UI fails clearly if the backend is down. · Startup time unmeasured. · Required. · Local is not "certified on-prem." · Process id and port.

### S4. Local inference
`ENVIRONMENT_BLOCKED` · See B1 and R2. · Benchmarks blocked. · Ship a CPU fallback and an optional GPU path with hashes of the weights. · Q2, R2. · Checkpoints the license allows redistributing. · ToothInstanceNet. · Offline inference on the official case matches the stored semantic contract within a reviewed tolerance, or the difference is explained. · Unmeasured on this host. · Required for the segmentation claim. · Local inference is still `REQUIRES_REVIEW`. · Weight hashes.

### S5. GPU compatibility
`ENVIRONMENT_BLOCKED` · No product GPU probe. · Benchmark host records. · A startup probe that records device, driver, and fallback. · R2. · GPU and CPU machines. · Runtime probe. · A machine without a GPU still opens a case. · Unmeasured. · Required. · Probe output is operational. · Device log.

### S6. CPU fallback
`NOT_IMPLEMENTED` · ToothInstanceNet device can be set to CPU in the adapter and was not accepted as a product path here. · Adapter device flag. · A tested CPU segmentation or a hard stop that says GPU is required, chosen from evidence. · S5. · CPU. · Adapter. · The choice is visible in the UI. · Unmeasured. · Required. · Fallback does not change truth class. · Device string.

### S7. Packaging choice
`NOT_IMPLEMENTED` · No Electron, Tauri, or native shell in product dependencies. `electron-to-chromium` in the lockfile is a browserslist transitive, not a shell. · Repository search. · A measured trial. No default choice in this plan. · S1. · Prototype installs. · Candidates only. · The chosen shell is removable. · Comparison required. · Decision required before the gate. · The choice is engineering. · Trial report.

### S8. Updates
`NOT_IMPLEMENTED` · Git updates only. · None. · An update story that does not strand cases. · S1, A13. · Installer. · Undecided. · An update preserves case hashes. · Unmeasured. · Required before calling the app shippable. · Update is not a clinical change. · Version pair.

### S9. Logs
`IMPLEMENTED_BUT_PARTIAL` · API logs exist as a developer server. No log policy. · Runtime behavior, not a product log design. · A rotating local log without scan contents. · A14. · Local disk. · Standard logging. · A test or review shows meshes are not dumped into logs. · Not a hot path. · Required. · Logs are operational. · Log policy version.

### S10. Desktop crash recovery
`NOT_IMPLEMENTED` · See O9 for the API. No shell crash path. · None. · Restore the last case after a killed shell. · O9, S1. · Local store. · Shell plus API. · The case hash after recovery matches the last commit. · Unmeasured. · Required. · Recovery does not replay an uncommitted gizmo drag. · Last version id.

### S11. Case storage
`IMPLEMENTED_BUT_PARTIAL` · Files under env-configured directories. · Store code and reliability tests. · A user-visible case folder with permissions documented. · A13, S12. · Disk. · Current store, then the installer path. · Backup of the folder restores the case. · Not a hot path. · Required. · Storage location is not anonymity. · Path and schema.

### S12. Filesystem permissions
`NOT_IMPLEMENTED` · The developer user can read the repo. No product permission model. · None. · The app requests only its case directory and the user's chosen scan folder. · S11. · OS permissions. · Shell. · A denied folder produces a visible error. · Not a hot path. · Required. · Permission failure is operational. · Path requested.

### S13. Offline operation
`IMPLEMENTED_BUT_PARTIAL` · The stack can run on localhost with no product telemetry identified in this audit. Models and weights are not bundled. · API can serve local cases. · A documented offline mode that opens an existing case with no network. · S3, S4. · Local case. · Installer. · Airplane-mode open, edit, and export of a previously segmented case. · Unmeasured. · Required. · Offline does not fetch a model. · Mode flag.

---

## Status counts

These counts are planning inventory, not a score.

| Status | Rows (primary) |
|---|---|
| `IMPLEMENTED_AND_VERIFIED` | 63 |
| `IMPLEMENTED_BUT_PARTIAL` | 95 |
| `IMPLEMENTED_BUT_NOT_WORLD_CLASS` | 15 |
| `IMPLEMENTED_BUT_NOT_PROVEN` | 6 |
| `PLACEHOLDER` | 1 |
| `NOT_IMPLEMENTED` | 111 |
| `NOT_AVAILABLE_BY_DATA` | 8 |
| `REQUIRES_REAL_DATA` | 1 |
| `REQUIRES_EXTERNAL_TECHNOLOGY` | 3 |
| `ENVIRONMENT_BLOCKED` | 3 |
| Total | 306 |

Six rows also carry a second gate: real segmentation and the segmentation model are `ENVIRONMENT_BLOCKED`; occlusion visualization and upper/lower registration are `NOT_AVAILABLE_BY_DATA`; roots and the CBCT pathway are `REQUIRES_REAL_DATA`. `FIXTURE_ONLY` is not a primary status. Fixture mode exists and is fenced, and it is not the implementation of a clinical capability. `REQUIRES_HUMAN_ACCEPTANCE` is a gate on clinical and manufacturing sign-off, not a row status: the product must not grant it.

Nothing in this table is First Version ready.
