# WP-10 — Production CAD

**Work package:** FIRST VERSION WP-10  
**Verdict:** **PASS** — Production CAD honesty boundary plus evidence-backed ProductionGeometryAdapter (trimesh inspection, Manifold validity/booleans, MeshLib engineering offset). Trimline / undercut / manufacturing certification remain `NOT_AVAILABLE`. Engineering offset is `REQUIRES_REVIEW` — never manufacturing certified or clinically approved.

**WP-11 and all later work packages were NOT started.**

---

## 1. Verdict

PASS.

Delivered (WP-10 + technology evaluation remediation):

- Persisted `ProductionPlan` contract (`production_cad_1.0`) with binding, readiness, QC, parameters, provenance, limitations.
- Explicit production source selection (never silent stage choice).
- Source clinical geometry vs derived treatment-stage fingerprints separated.
- Mesh integrity QC on treatment meshes (technical only — not manufacturing readiness).
- **ProductionGeometryAdapter** isolating Current / trimesh / Manifold / MeshLib backends.
- MeshLib engineering offset sample on selected source (truth `REQUIRES_REVIEW`; not manufacturing certified).
- Manifold validity gate (real crowns typically `NotManifold`) + engineering solid booleans.
- Trimline / undercut / manufacturing certification → `NOT_AVAILABLE`.
- Component readiness (no single `manufacturing_ready=true`).
- Validation 2.0 consumed; unavailable checks never treated as PASS.
- Engineering export package + independent ZIP hash verify/reopen reused.
- Technology evaluation documented with measured real-case benchmarks.

Remaining honest gaps (not blockers to WP-10 completion after tech gate):

- Trimline / undercut / manufacturing QC certification unavailable.
- Engineering offset is voxelized and requires human review; not a material-validated aligner thickness claim.
- Full per-tooth production shell package export is not claimed as manufacturing-ready.

---

## 2. Existing production audit

| Area | Pre-WP-10 | Reuse |
|---|---|---|
| P5 ManufacturingBoundaryReport | Honest unavailable shell/trimline/QC | **Preserved** + embedded in ProductionPlan |
| TreatmentExportEngine | Stage STLs, manifest, hash verify/reopen | **Preserved** — sole export engine |
| Export API `/export`, `/export/verify`, `/export/reopen` | Engineering package | **Preserved** |
| GeometricValidationEngine | Sole geometric authority | **Preserved** (not replaced) |
| Validation 2.0 | Check catalog + freshness | **Consumed** by ProductionPlan |
| Clinical tools / staging / setup versions | Session binding | **Bound** into production |
| ProductionPanel / manufacturingBoundary | Boundary UI | **Extended** with productionCad |
| Mesh boolean/offset libraries | None suitable for appliance CAD | Shell remains NOT_AVAILABLE |

No duplicate export/manufacturing systems created.

---

## 3. ProductionPlan architecture

`domain/treatment_plan/production_cad.py` + `engines/export/production_cad_engine.py`

Contract fields include: `production_plan_id`, `production_version_id`, `parent_production_version_id`, case/setup/staging/clinical-tools/validation binding, selected stage + source kind, source/derived hashes, operations, readiness, QC checks, parameters, manufacturing boundary, export state, truth/freshness, algorithm/version, limitations, timings.

Session fields: selected stage/kind, production version lineage, bound setup/staging/tools/validation versions for staleness.

API:

- `POST /cases/{id}/production/source`
- `POST /cases/{id}/production/source/clear`

Review bundle: `productionCad` alongside `manufacturingBoundary` + `validationCapability`.

---

## 4. Source-state selection

Doctor must select explicitly:

- `selected_stage` / `final_target` / `explicit_treatment_state`
- Default without selection: `unselected` → readiness `requires_review`

Silent auto-selection of a manufacturing stage is forbidden.

---

## 5. Production geometry boundary

1. Clinical treatment geometry (setup `source_vertices`) — never mutated by Production CAD.
2. Production preparation — derived stage mesh fingerprints + engineering export artifacts.
3. Export artifact — TreatmentExportEngine ZIP (treatment stage models), not appliance shells.

---

## 6. Mesh integrity

Per inspected stage tooth mesh:

- finite coordinates
- non-empty vertices + faces (`source_faces` / `final_target_faces`)

Reported as independent QC check. Passing ≠ manufacturing-ready.

---

## 7. Shell generation

**Engineering offset (MeshLib):** When MeshLib is available and a production source is explicitly selected, a **sample** engineering voxel offset is computed for one tooth of the selected stage.

- Truth: `REQUIRES_REVIEW`
- `shell_generated` may be `true` for that sample
- `manufacturing_certified` / `clinically_approved` remain `false`
- Distance is a **technical** parameter (default 0.2 model units), not a clinical thickness recommendation

**Manifold:** Real crown meshes are typically open / non-manifold solids → Manifold rejects import (`Error.NotManifold`). Manifold is **not** used as an appliance shell engine.

**Trimline / material profile / undercut:** remain `NOT_AVAILABLE`.

---

## Production CAD Technology Evaluation

### 1. Current implementation audit (pre-remediation)

| Capability | Status | Implementation |
|---|---|---|
| Mesh loading | PARTIAL | trimesh (upload/segmentation); Three.js STLLoader (viewer) |
| Mesh representation | AVAILABLE | Domain vertex/face tuples + numpy + trimesh |
| Mesh integrity | PARTIAL | Finite/non-empty in production_cad; face indices in export/validation |
| Topology / watertight | PARTIAL | trimesh flags on upload only (non-blocking); not in WP-10 QC originally |
| Self-intersection (single mesh) | NOT_AVAILABLE | Inter-tooth collision exists in GeometricValidationEngine |
| Repair / remesh / smooth / decimate | NOT_AVAILABLE | — |
| Boolean / offset / shell | NOT_AVAILABLE | Honesty layer only |
| Export / verify | AVAILABLE | TreatmentExportEngine ASCII STL + ZIP hash audit |
| Provenance | AVAILABLE | ProductionPlan binding + hashes |

### 2–9. Candidates evaluated

| Technology | Decision | Why |
|---|---|---|
| **Manifold / manifold3d 3.5.3** | **ADOPT** | Deterministic engineering booleans; manifold validity gate. Real crowns NotManifold — documents why Manifold cannot own open-surface shells. |
| **MeshLib 3.1.4.297** | **ADOPT** | Measured engineering offset on real tooth → watertight volume, deterministic; self-intersection query; boolean. Isolated behind adapter. |
| **trimesh 5.1.0** | **ADOPT (keep)** | Already used; expanded for watertight/winding inspection in Production QC. |
| **Open3D** | **REFERENCE** | Overlaps trimesh+MeshLib; not installed this gate; no unique measured Production CAD gap. |
| **CGAL** | **REFERENCE** | Heavy C++ stack; covered by Manifold+MeshLib for evaluated ops. |
| **libigl** | **REFERENCE** | Research-oriented; duplicates covered capabilities. |
| **Current integrity** | **ADOPT (keep)** | Sufficient for finite/non-empty checks. |

### 10–12. Benchmark methodology and evidence

- Script: `scripts/wp10_production_cad_tech_benchmark.py`
- Geometry: `official_real_case_stage2_verified_v1` tooth instance (not fixture substitution)
- Synthetic solids used **only** for boolean smoke tests and labeled `synthetic_engineering`
- Machine-readable decisions: `docs/WP10_PRODUCTION_CAD_TECH_EVAL.json`
- Benchmark output: `.research/tmp/wp10_tech_evaluation_benchmark.json`

Measured (representative; see JSON for exact run):

| Operation | Backend | Result |
|---|---|---|
| Integrity | current | success on real tooth |
| Watertight/winding | trimesh | real tooth: watertight=false, winding=true |
| Manifold validity | manifold3d | real tooth: `Error.NotManifold` |
| Self-intersection | meshlib | 0 colliding pairs on sample tooth |
| Engineering offset | meshlib | success; watertight volume output; deterministic hash match |
| Boolean | manifold3d / meshlib | success on synthetic solids |

### 13–17. Capability decisions and adapter

```
Production CAD
  → ProductionGeometryAdapter
      ├── CurrentIntegrityBackend
      ├── TrimeshInspectionBackend
      ├── ManifoldBackend
      └── MeshLibBackend
```

ProductionPlan remains the application contract. Geometry backends/operations/versions/hashes recorded on the plan payload.

### 18–22. Performance, determinism, provenance, limitations

- Engineering offset ~80–170 ms per tooth sample (voxelSize dependent)
- Manifold boolean on synthetic solids ≪ 1 ms; MeshLib boolean ~8 ms
- Offset hash determinism: matched on repeated runs
- Source vertex/face bytes unchanged after offset
- Limitations: trimline/undercut/certification unavailable; offset is engineering REQUIRES_REVIEW; arch scans are open non-volumes
- Environment: MeshLib/Manifold must be installed in the API/runtime venv (`services/api/pyproject.toml`)

**Explicit statements:**

- No library was added merely because it is popular.
- No technically superior technology was rejected merely because it was external.
- Every adopted technology has evidence.
- Unsupported manufacturing operations remain NOT_AVAILABLE where not implemented.
- Manufacturing certification is not claimed.

---

## 8. Trimline

**NOT_AVAILABLE.** No fake production trimline.

---

## 9. Undercut

**NOT_AVAILABLE.** No fabricated clearance.

---

## 10. Manufacturing parameters

Explicit parameters with unset values:

| Name | Value | Kind | Notes |
|---|---|---|---|
| shell_thickness | null | manufacturing | not_configured; not clinical recommendation |
| trimline_offset | null | manufacturing | not fabricated |
| undercut_clearance | null | manufacturing | not fabricated |

Each carries unit, source, configuration version, provenance, limitations.

---

## 11. Production QC

Independent checks (examples):

- source_binding
- validation_binding
- setup_staging_binding
- clinical_tools_binding
- mesh_integrity
- shell_generation / trimline / thickness_profile / undercut_analysis → not_available
- manufacturing_qc_certification → not_available
- occlusion_dependency → not_available when occlusion unavailable
- export_validation (engineering package integrity capability)

No collapsed manufacturing score. No `manufacturing_certified=true`.

---

## 12. Export validation

Pipeline reused:

Production boundary → TreatmentExportEngine.export → ZIP → verify_package / reopen_for_audit

Independent checks: file exists, format, hashes, manifest integrity, provenance metadata. Export success ≠ manufacturing certification. Session re-import from ZIP alone remains unavailable (audit reopen only).

---

## 13. Re-import / reopen

- Editable production state: session ProductionPlan selection + treatment session.
- Exported artifact: ZIP package.
- Re-imported verification: `reopen_for_audit` / `verify_package` — not editable clinical plan.

---

## 14. Export package

Deterministic engineering treatment export (existing): stage geometry, reports, manufacturing boundary notes, provenance. Missing appliance CAD is stated via boundary + ProductionPlan readiness (`shell`/`trimline`/… = not_available). No placeholder shell geometry in package.

---

## 15. Truth states

| State | Meaning |
|---|---|
| COMPUTED | Deterministic production boundary / treatment mesh QC computed |
| REQUIRES_REVIEW | Unselected source, stale versions, or review-required dependencies |
| NOT_AVAILABLE | Unsupported manufacturing operation |
| VERIFIED | Reserved for genuine independent verification — never set solely because export succeeded |

`manufacturing_ready` / `manufacturing_certified` / `clinically_approved` always false in payload.

---

## 16. Versioning / staleness

Committed production selection stores bound setup/staging/clinical-tools/validation ids. Drift → `freshness=stale`; committed `production_version_id` preserved until explicit re-selection (new version + parent lineage).

---

## 17. Validation integration

Consumes Validation 2.0 run id + freshness. Unavailable clinical checks remain visible upstream; production does not treat them as PASS. Does not auto-block engineering stage export for every unavailable check unless that capability is required for the specific operation (shell would require manufacturing CAD → remains unavailable).

---

## 18. Clinical-tools integration

Binds clinical_tools setup/staging version ids. Tool state exposed as requires_review / not_available — not silently ignored as manufacturing prescriptions.

---

## 19. Occlusion limitations

Occlusion unavailable → explicit QC limitation. Does not block unrelated stage-model engineering export.

---

## 20. Provenance

Plan records algorithm/version, binding versions, source/derived hashes, fixture flag, provenance from proposal, limitations, manufacturing boundary payload.

---

## 21. Real-case evidence

Case: `official_real_case_stage2_verified_v1` (28 semantic teeth, no FDI).

Evidence file (written by test when artifact present): `.research/tmp/wp10_real_case_evidence.json`

Observed capability states (from evidence JSON after tech gate):

| Capability | State |
|---|---|
| Source selection | `final_target`, stage_index=1 |
| Shell | `requires_review` (MeshLib engineering offset sample; `shell_generated=true`) |
| Trimline | not_available |
| Thickness | requires_review technical distance only — not material profile |
| Undercut | not_available |
| Mesh QC | available (treatment meshes; not manufacturing cert) |
| Engineering export + verify | verified=true |
| Manufacturing certified | false |
| FDI fabricated | false |
| Fixture substituted into REAL_CASE production claims | false |

Source `source_vertices` unchanged across production plan build.

---

## 22. Performance

Measured on `official_real_case_stage2_verified_v1` (evidence + tech benchmark JSON):

| Metric | Value |
|---|---|
| Production plan build (with MeshLib sample offset) | ~578 ms (`production_cad_ms`) |
| MeshLib engineering offset (tooth sample) | ~80–170 ms |
| Manifold validity (tooth) | ~1–2 ms (`NotManifold`) |
| trimesh inspect (tooth) | ~13 ms |
| Compose / export / verify | see `.research/tmp/wp10_real_case_evidence.json` per run |

Engineering offset is REQUIRES_REVIEW — not manufacturing certification.

Shell/offset time: N/A (unavailable).

---

## 23. Tests

`tests/python/test_wp10_production_cad.py` covers:

ProductionPlan contract, source selection, bindings, versioning/staleness, source immutability/hashes, mesh identity/QC, shell/trimline/undercut unavailable, parameters, QC, export verify/reload, no fake export, API select/clear, review bundle, no FDI fabrication, occlusion limitation, GeometricValidationEngine preserved, real-case evidence, WP-09 + P5 regressions.

---

## 24. Limitations

- No appliance shell / trimline / undercut CAD.
- No manufacturing material or thickness certification.
- Engineering export is treatment geometry audit package.
- Crown-only real case cannot support occlusion-dependent manufacturing claims.
- No session restoration from export ZIP alone.

---

## 25. Environment blockers

- Official real-case artifact required for real-case evidence test (`official_real_case_stage2_verified_v1` dir or zip).
- No mesh boolean library integrated for production shells.

---

## 26. Explicit stop confirmation

**WP-11 and all later work packages were NOT started.**  
No global UX redesign. No desktop packaging. No new research model integration. No final real-case gate work begun.
