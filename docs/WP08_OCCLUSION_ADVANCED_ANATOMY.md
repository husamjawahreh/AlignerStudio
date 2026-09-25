# WP-08 — Occlusion + Advanced Anatomy

**Work package:** FIRST VERSION WP-08  
**Verdict:** **PASS WITH BLOCKER** — occlusion and advanced-anatomy capability contracts, registration gates, geometric-contact semantics, provenance/staleness, and setup/staging prerequisite wiring are implemented; genuine bite registration and root/CBCT anatomy remain unavailable on the official crown-only artifact (honest `unavailable` / `not_available`).

**WP-09 and all later work packages were NOT started.**

---

## 1. Verdict

PASS WITH BLOCKER.

Delivered:

- Explicit occlusion capability contract (`occlusion_1.0`) with states: `unavailable`, `source_registered`, `computed`, `requires_review`, `verified`.
- Explicit advanced-anatomy capability contract (`advanced_anatomy_1.0`) distinguishing crown / root / landmarks / clinical axes / generic geometric directions / CBCT volumetric.
- Registration evidence parser that accepts only genuine provenance-bearing inputs; never invents bite from dual-arch presence.
- Geometric contact candidates labeled as geometric/candidate only — never clinical occlusal diagnosis.
- Arch relationship clinical descriptors (Class I/II/III, OJ/OB, etc.) remain `unavailable` without validated methods.
- Provenance, version binding, and staleness detection for source hashes / registration / setup / staging.
- Treatment Setup / Staging readiness consumes WP-08 capability state as explicit prerequisites (does not globally disable unrelated planning).
- Analysis UI surfaces occlusion capability, registration state, and advanced-anatomy honesty rows.
- Real-case evidence on `official_real_case_stage2_verified_v1` proving unavailable occlusion/roots/landmarks/clinical axes.
- GeometricValidationEngine remains the authority for staging intra-arch validation; cross-arch occlusion is a separate capability path.

Blocker (environmental / evidence, not a process failure):

- Official real case is crown-only STL with **no genuine bite registration**.
- No CBCT/volumetric pathway is implemented (capability contract only).
- No clinical axis / landmark fabrication was performed — they remain not available.

---

## 2. Existing capability audit

| Area | Pre-WP-08 state | Reuse |
|---|---|---|
| WP-02 `unavailable_occlusion()` / DI occlusion truth | Always NA for crown STL | **Extended** — still default path; richer payload |
| `OcclusionRepresentation` availability enums | Stub only | **Preserved** + capability state wrapper |
| `AnatomyExtent` / `root_bone` gate | Crown vs CBCT boundary | **Reused** |
| ToothIntelligence root/landmarks/clinical axes / mesh PCA | Per-tooth truth | **Reused** as anatomy inputs |
| GeometricValidationEngine | Intra-arch only; cross-arch skipped | **Preserved** — not replaced |
| Setup / Staging readiness `occlusion` / `clinical_axes` | Hard-coded NOT_AVAILABLE | **Wired** to WP-08 when evidence exists |
| AnalysisPanel occlusion / measurements | Showed NA | **Enriched** with capability + advanced anatomy |
| 3D OcclusionLayer | Empty, disabled | Unchanged (no fabricated overlays) |
| Registration / ICP libraries | None in product | **Not invented** — evidence contract only |
| WP-07 clinical tools contract pattern | Truth/freshness/binding | **Followed** for occlusion/anatomy |

---

## 3. Capability model

### Occlusion (`domain/tooth/occlusion.py`, `engines/occlusion/capability_engine.py`)

| State | Meaning |
|---|---|
| `unavailable` | No genuine registration/bite evidence |
| `source_registered` | Registration accepted with method/version + quality |
| `computed` | Geometric proximity/candidates computed from registered geometry |
| `requires_review` | Evidence incomplete or candidates need doctor review |
| `verified` | Reserved — never assigned from generation alone |

Every result carries readiness gates (registration / occlusion / geometric_contacts / arch_relationship), freshness, provenance, limitations, and `clinically_approved: false` / `occlusion_validated: false`.

### Advanced anatomy (`domain/tooth/advanced_anatomy.py`)

| Capability | Clinical? | Typical crown-only outcome |
|---|---|---|
| `crown_geometry` | No | `computed` |
| `root_geometry` | Yes | `not_available` |
| `landmark_geometry` | Yes | `not_available` |
| `clinical_axes` | Yes | `not_available` |
| `generic_geometric_axes` | No | `computed` (mesh PCA) |
| `cbct_volumetric_anatomy` | Yes | `not_available` |

---

## 4. Registration

Accepted evidence kinds (explicit only):

- `explicit_transform`
- `bite_scan`
- `common_coordinate_frame`
- `source_metadata`

Requirements for promotion beyond `requires_review`:

- method + method_version
- quality_metric + quality_metric_kind with `quality_established=true`

Never:

- Infer registration because upper+lower exist
- Fabricate RMSE / quality numbers
- Destructively transform source meshes (transform stored separately; applied only to measurement copies)

---

## 5. Occlusion computation

When genuine registration exists **and** a caller-supplied technical proximity threshold is provided:

- Centroid-distance geometric proximity between upper/lower tooth refs
- Results labeled `geometric_proximity` or `candidate_contact`
- Unit: `model units` (not claimed as mm)
- Threshold kind: `caller_supplied_geometric_proximity` (technical, not clinical)

Without registration → no computation → `unavailable`.

---

## 6. Contact / proximity semantics

| Term | Meaning |
|---|---|
| geometric proximity | Technical distance within caller threshold |
| candidate contact | Closer geometric candidate (still technical) |
| clinical occlusal contact | Reserved; never assigned without validated clinical method |

`clinical_interpretation` and `clinical_diagnosis` are always `null` on geometric candidates.

Staging `ContactResult` from GeometricValidationEngine remains **intra-arch** and is not relabeled as occlusal.

---

## 7. Advanced anatomy model

Capability report binds case_id, anatomy_extent, per-capability truth/source/hash/algorithm/limitations/provenance. Downstream consumers use `OcclusionAnatomyPlan` prerequisites.

---

## 8. Root handling

Crown-only STL → `root_geometry = not_available`.  
Roots are never reconstructed from crowns.  
CBCT root pathway remains gated by `AnatomyExtent.ROOT_BONE_CBCT` / `root_bone_pathway_supported`.

---

## 9. Landmark handling

No upstream landmarks on official artifact → `not_available`.  
Centroids / bounding-box extrema are **not** labeled clinical landmarks.

---

## 10. Dental-axis handling

Clinical axes → `not_available` on crown-only path.  
Mesh PCA / engineering frames → `generic_geometric_axes` with `clinical=false`.  
Never convert PCA into clinical dental axes.

---

## 11. CBCT / volumetric handling

No DICOM ingest in product. Capability contract only; state `not_available`.  
No inference of CBCT anatomy from surface STL.

---

## 12. Validation integration

- GeometricValidationEngine unchanged and authoritative for staging geometry checks.
- Occlusion never claims “occlusion validated” from geometric proximity.
- Cross-arch staging pairs remain skipped in GeometricValidationEngine (by design).

---

## 13. Setup / staging integration

`OcclusionAnatomyPlan` exposes prerequisites:

- occlusion
- clinical_axes
- root_geometry
- landmarks

Treatment Setup readiness maps these into `readiness.occlusion` / `readiness.clinical_axes`.  
Unavailable occlusion does **not** globally block unrelated planning.

Review bundle includes `occlusionAnatomy`.

---

## 14. Versioning / staleness

Occlusion binds:

- source input hash
- upper / lower mesh sha256
- registration_version_id
- optional setup / staging version ids

`evaluate_occlusion_freshness` → `current` | `stale` | `unavailable`.  
Source hash change marks dependent occlusion stale; recompute rebuilds against current inputs.

---

## 15. Provenance

Every occlusion/anatomy result preserves case_id, source artifacts/hashes, registration source, algorithm/method/version, input/output versions, truth state, limitations, timestamp, fixture/provenance flags. No fabricated provenance.

---

## 16. Real-case evidence

| Item | Value |
|---|---|
| Official artifact | `official_real_case_stage2_verified_v1` |
| Path | `.research/tmp/official_real_case_stage2_verified_v1/` (+ zip at repo root) |
| Contents | `upper.stl`, `lower.stl`, instance JSON, manifest — **no bite, no roots, no CBCT** |
| Arch registration | **unavailable** (`evidence_kind=none`) |
| Occlusion state | **unavailable** |
| Contact/proximity | **unavailable** (not computed) |
| Root | **not_available** |
| Landmarks | **not_available** |
| Clinical axes | **not_available** |
| Generic geometric directions | **computed** (mesh PCA) when geometry present |
| Crown geometry | **computed** |
| CBCT / volumetric | **not_available** |
| Truth-state distribution | Occlusion NA; crown computed; clinical anatomy NA |
| Provenance | Fixture-marked test path over verified artifact; not silent REAL substitution |
| Stale-state | Detected when bound upper/lower hash diverges |
| Persistence/reopen | Dental intelligence stores enriched occlusion.value + advanced_anatomy |

No invented clinical measurements or diagnoses.

---

## 17. Performance

Measured in `test_performance_measurements_recorded` on this machine (unavailable-registration path; not optimized):

| Operation | Measured |
|---|---|
| Registration gate | ~0.05 ms (`timings_ms.registration_ms`) |
| Contact/proximity (skipped when unavailable) | ~0.004 ms |
| Occlusion total | ~0.14 ms (`timings_ms.total_ms`) |
| Anatomy capability | ~0.17 ms (`timings_ms.anatomy_capability_ms`) |
| Wall (occlusion+anatomy) | ~0.38 ms |

Artifact load / intelligence build dominates end-to-end test wall time (~6–12 s per real-case test) and is outside the occlusion gate itself. No invented FPS/product claims. No premature optimization.

---

## 18. Tests

| Path | Coverage |
|---|---|
| `tests/python/test_wp08_occlusion_advanced_anatomy.py` | Capability contract, unavailable occlusion, crown-only anatomy, root/landmark/axis NA, PCA non-clinical, no FDI fabrication, no synthetic clinical use, artifact binding, registration provenance/staleness, contact identity/semantics, no fabricated diagnoses/roots/landmarks/axes, setup integration, persistence, API, recompute, performance, fixture marking |
| Prior WP suites | WP-01…WP-07 and P0–P8 remain intact (not reimplemented) |

---

## 19. Limitations

- No genuine bite registration on official artifact → occlusion stays unavailable in production evidence path.
- Geometric contact candidates (when registration injected in tests) use centroid distance — not mesh surface occlusion analysis.
- No Class/OJ/OB clinical interpretation.
- No CBCT ingest.
- 3D occlusion overlays remain empty (no fabricated contact spheres).
- `verified` occlusion is never auto-assigned.

---

## 20. Environment blockers

- Live REAL_CASE GPU segmentation path still environment-dependent (unchanged from prior WPs).
- Official artifact lacks bite/registration evidence — expected blocker for unlocking occlusion.
- No ICP/Open3D registration product engine (intentionally not invented).

---

## 21. Explicit confirmation

**WP-09 (Validation 2.0), Production CAD (WP-10), WP-11 global UX redesign, and all later work packages were NOT started.**  
No new research models (including 3DTeethSAM / new CBCT models) were integrated.
