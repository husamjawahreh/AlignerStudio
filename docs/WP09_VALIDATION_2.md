# WP-09 — Validation 2.0

**Work package:** FIRST VERSION WP-09  
**Verdict:** **PASS WITH BLOCKER** — Validation 2.0 contract, honesty layer, unavailable-check catalog, version binding/staleness, and review UI are implemented over GeometricValidationEngine; clinical interpretation, manufacturing QC, and occlusion-dependent validation remain unavailable/review-required on crown-only evidence.

**WP-10 and all later work packages were NOT started.**

---

## 1. Verdict

PASS WITH BLOCKER.

Delivered:

- Versioned Validation 2.0 contract (`validation_2.0`) with ValidationRun / ValidationFinding / check catalog.
- GeometricValidationEngine remains the sole geometric authority (not replaced).
- Explicit PASS / WARNING / ERROR / INVALID / NOT_AVAILABLE / REQUIRES_REVIEW check states.
- Unavailable capability checks (occlusion, roots, clinical axes, landmarks, manufacturing) remain visible as `not_available` — never PASS.
- PASS ≠ clinical approval (`clinically_approved: false`, `pass_means_clinical_approval: false`, `clinical_safety_guarantee: false`, no validation score).
- Setup / staging / clinical-tools version binding + freshness (`current` / `stale` / `unavailable`).
- Post-edit revalidation via existing WP-04 restage→validate path.
- Review bundle exposes `validationCapability` alongside legacy `validationSummary`.
- ValidationPanel shows check catalog, unavailable/review groups, findings, freshness, provenance.
- Findings carry tooth-pair `spatial_binding` for selection/focus (no invented heatmaps).

Blocker (evidence / scope):

- Official real case has no occlusion/roots/axes/landmarks → those checks stay unavailable.
- Manufacturing QC deferred (WP-10).
- No clinical thresholds invented.

---

## 2. Existing validation audit

| Area | Pre-WP-09 | Reuse |
|---|---|---|
| GeometricValidationEngine | Authoritative mesh collision/proximity/contact | **Preserved** |
| Cross-arch skip | Same-arch only | **Preserved** |
| P5 ValidationReviewSummary | Honest category strings | **Preserved** as legacy + embedded |
| TreatmentValidationReport | Session-persisted geometric report | **Preserved** |
| WP-04 edit→restage→validate | Coupled recalculation | **Preserved** |
| WP-05/06 readiness.validation | Report presence gate | **Preserved** |
| WP-07/08 capability contracts | Truth/freshness/binding pattern | **Followed** |
| ValidationPanel | Stage counts + summary | **Extended** |
| 3D ValidationLayer | Empty / disabled | **Hooks only** via spatial_binding |

---

## 3. Validation 2.0 model

`domain/treatment_plan/validation_v2.py` + `engines/validation/validation_v2_engine.py`

`ValidationRun` binds case, setup/staging/clinical-tools/occlusion versions, geometric report id, config hash, algorithm/version, findings, checks, summary, thresholds, limitations, timings.

---

## 4. Finding categories

Supported (actually backed):

- collision / proximity / contact (GeometricValidationEngine)
- geometry_data_quality
- source_consistency / treatment_state_consistency / staging_consistency
- clinical_tool_consistency
- occlusion_capability
- movement_constraints
- root_anatomy / clinical_axes / landmarks
- manufacturing_readiness

No invented clinical diagnosis categories.

---

## 5. Severity

Technical: `info` | `warning` | `error`  
Never auto-mapped to clinical urgency.

---

## 6. Truth states

| State | Usage |
|---|---|
| COMPUTED | Deterministic geometric engine finding/check |
| REQUIRES_REVIEW | Human review required |
| NOT_AVAILABLE | Required evidence/method absent |
| VERIFIED | Never assigned merely because the engine ran |

---

## 7. Unavailable checks

If roots / clinical axes / occlusion / manufacturing / clinical thresholds are missing:

→ check_state = `not_available`  
→ remains in catalog  
→ never PASS

---

## 8. Thresholds

Caller-supplied `GeometricValidationConfiguration` values recorded as **technical** thresholds with engine version.  
Unit: model units.  
`clinical_limit: false`.

Default session config (unchanged): proximity=1.0, contact=0.001, collision=0.0, engine_version=`phase7-geometric-validation-1`.

---

## 9. Version / context binding

Contexts: source / target / stage / clinical_tools / production_export / case.  
Binding fields: setup_version_id, staging_version_id, clinical tools versions, occlusion registration version, geometric report id, mesh/input hashes, config hash.

---

## 10. Staleness

`evaluate_validation_freshness` → stale when bound setup/staging/clinical-tools/report ids diverge from current.

---

## 11. Post-edit behavior

Doctor edit → target update → staging rebuild → GeometricValidationEngine.validate → new Validation 2.0 run in review_bundle.  
Stale presentation avoided by recomputing capability on each review.

---

## 12. Staging validation

Per-stage findings keep `stage_index` + context_kind=`stage`.  
Final vs intermediate contexts remain distinct via stage index.

---

## 13. Clinical-tool validation

Clinical-tool consistency check is `requires_review` when tools are bound; unavailable when unbound.  
Does not clinically approve IPR/attachments.

---

## 14. Occlusion interaction

Occlusion unavailable → occlusion_capability check = `not_available`.  
Never converted to PASS.  
Intra-arch geometric contacts are not relabeled as occlusal diagnoses.

---

## 15. 3D visualization hooks

Findings include `spatial_binding: {kind: tooth_pair, tooth_a, tooth_b, stage_index}` for selection/focus.  
ValidationLayer remains without invented heatmaps/regions.

---

## 16. Review UI

ValidationPanel (WP-09):

- Summary counts: passed / warnings / errors / unavailable / review
- Freshness + overall check/truth state + run id
- Full check catalog
- Unavailable and review-required groups
- Findings list with tooth refs / stage
- Provenance + geometric engine version
- Explicit “PASS is not clinical approval” copy

Legacy `validationSummary` retained for compatibility.

---

## 17. Provenance

Run preserves case, versions, report id, config hash, algorithm/version, geometric engine version, timestamps, fixture flag, limitations.

---

## 18. Real-case evidence

| Item | Value |
|---|---|
| Artifact | `official_real_case_stage2_verified_v1` |
| Geometric checks | Executed via GeometricValidationEngine on composed staging |
| Occlusion / roots / axes / landmarks / manufacturing | **not_available** |
| PASS ≠ clinical approval | Enforced in payload flags |
| Version binding | setup/staging/report ids present |
| Stale detection | Covered by unit tests |
| Post-edit | Restage regenerates validation |
| Persistence | Session pickle reopen retains geometric report |

---

## 19. Performance

Measured in `test_performance_measurements` (honesty-layer wrap of an already-composed geometric report):

| Metric | Value |
|---|---|
| Validation 2.0 wrap | ~0.64 ms (`timings_ms.validation_2_ms`) |
| Wall | ~0.67 ms |
| Check count | 14 |
| Unavailable checks | 7 |
| Finding count | includes geometric findings + unavailable capability findings |

GeometricValidationEngine runtime remains the P0/Phase-7 path (unchanged). No invented product FPS claims.

---

## 20. Tests

`tests/python/test_wp09_validation_2.py` — contract, severity/truth, PASS vs NA vs clinical approval, occlusion NA, staleness, post-edit, clinical tools, thresholds, pair identity, review bundle, geometric authority, real-case unavailable checks, persistence, fixture marking, performance.

Prior WP / P0 geometric suites remain authoritative regressions.

---

## 21. Limitations

- No clinical interpretation layer.
- No manufacturing QC (WP-10).
- No invented clinical thresholds.
- 3D overlays: binding only, no heatmap.
- Centroid/mesh geometric findings remain technical.

---

## 22. Environment blockers

- Official artifact lacks bite/registration/roots/CBCT.
- Live REAL_CASE GPU path unchanged / environment-dependent.

---

## 23. Explicit confirmation

**WP-10 (Production CAD), WP-11 global UX redesign, Desktop packaging, and all later work packages were NOT started.**  
No new research models were integrated.
