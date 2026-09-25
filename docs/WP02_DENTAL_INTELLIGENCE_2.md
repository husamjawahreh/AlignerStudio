# WP-02 — Dental Intelligence 2.0

**Work package:** FIRST VERSION WP-02  
**Date:** 2026-09-25  
**Authoritative roadmap:** `AlignerStudio_PRODUCTION_MASTER_PLAN_v2.1.md`  
**Active First Version plan:** `Aligner_Studio_First_Version_World_Class_Plan.md`  
**Foundation evidence:** `docs/FV01_PRODUCT_REALITY_AUDIT.md`, `docs/WP01_REAL_CLINICAL_DATA_PIPELINE.md`  
**Scope:** Truth-preserving clinical intelligence from genuine processed tooth instances.  
**Explicit stop:** **WP-03 and all later work packages were NOT started.**

---

## 1. Verdict

**PASS WITH BLOCKER** (same GPU/runtime blocker as WP-01).

- Dental Intelligence 2.0 is a real, persisted, versioned contract (`dental_intelligence_2.0`).
- It consumes genuine processed segmentation payloads (WP-01 `segmentation_results`).
- Truth states are explicit: `verified` / `computed` / `requires_review` / `not_available`.
- FDI, landmarks, clinical dental axes, roots, and occlusion are never fabricated.
- Mesh PCA principal directions are labeled geometric, never as clinical dental axes.
- Capability/readiness gates are machine-readable and do **not** auto-unlock Treatment Setup.
- Non-GPU intelligence layers are tested against the official real-case artifact geometry.
- Live ToothInstanceNet CUDA inference remains unavailable in this environment (no `torch` / no NVIDIA driver) — documented, not hidden.

This is **not** doctor-ready, production-ready, or world-class completion.

---

## 2. Scope completed

| Item | Status |
|---|---|
| Domain contracts (`TruthValue`, tooth/arch/case intelligence, readiness) | Done |
| Deterministic geometry metrics engine | Done |
| Dental Intelligence builder from WP-01 segmentation records | Done |
| Persistence (`case.dental_intelligence`) + API GET/rebuild | Done |
| Live TIN `tooth_ref` / `arch` stamping (no FDI invention) | Done |
| Analysis UI truth-state / readiness presentation | Done |
| Tests + real-case non-GPU evidence | Done |
| WP-03 3D workspace redesign | **Not started** |
| Treatment Setup / Staging / Validation product features | **Not started** |
| 3DTeethSAM / new research models | **Not started** |

---

## 3. Existing intelligence reused

- P3 `anatomical_intelligence` summary (availability flags, occlusion stub, data-quality report)
- WP-01 `segmentation_results` persistence (job_id, input_hash, per-arch tooth_instances, mesh hashes)
- Semantic identity / `tooth_ref` rules from P0/P3
- `unavailable_occlusion()` — still the sole occlusion representation for crown-only STL
- Geometric validation authority unchanged
- ToothInstanceNet retained as the segmentation baseline

WP-02 **extends** these; it does not fork or replace them.

---

## 4. New clinical intelligence contracts

| Contract | Location |
|---|---|
| `IntelligenceTruthState` | `domain/tooth/intelligence_v2.py` |
| `TruthValue[T]` | same |
| `GeometryMetrics` | same |
| `ToothIntelligence` | same |
| `ArchIntelligence` | same |
| `CapabilityReadiness` | same |
| `CaseDentalIntelligence` (`contract_version=dental_intelligence_2.0`) | same |
| TS mirrors | `packages/contracts/src/dentalIntelligence.ts` |

API:

- `GET /cases/{case_id}/dental-intelligence`
- `POST /cases/{case_id}/dental-intelligence/rebuild`

---

## 5. Data model

Per tooth (fields present only when supported; missing stays `not_available`):

- Stable `tooth_ref`, `instance_id`, `arch`
- Source mesh path + SHA-256
- Segmentation model name/version
- FDI / semantic label as `TruthValue`
- Geometry metrics (centroid, bbox, extents, area, volume, mesh PCA)
- Crown / root availability
- Landmarks, local frame, clinical dental axes (separate from mesh PCA)
- Quality findings, provenance, fixture flag, overall truth state

Case document also carries arches, occlusion, data-quality findings, capability readiness, timings, limitations.

---

## 6. Truth-state model

| State | Meaning |
|---|---|
| `verified` | Genuinely provided/validated clinical fact (never granted merely because code ran) |
| `computed` | Deterministically derived from valid source geometry/data — **not** clinical validation |
| `requires_review` | Potentially useful; needs human or stronger confirmation |
| `not_available` | Required source/method absent |

Silent promotion between states is forbidden.

---

## 7. Identity handling

- Verified FDI is **never invented**.
- Model-supplied FDI (when present) is `requires_review`, never auto-`verified`.
- Official real-case artifact is semantic-only → FDI `not_available`, stable `tooth_ref` retained.
- Live TIN stamps `tooth_ref = "{arch}:instance:{id}"` and arch without inventing FDI.
- Unknown identity remains unknown.

---

## 8. Arch intelligence

Per arch: tooth-instance count, resolved/unresolved FDI counts, geometry-ready count, landmarks/axes availability counts, quality findings, overall truth state, provenance, source mesh hash.

No clinical conclusions from tooth count alone.

---

## 9. Geometry-derived intelligence

`engines/arrangement/geometry_metrics.py` — deterministic mesh metrics:

- Bounding box, centroid, extents
- Surface area; volume when mesh yields a finite signed volume
- Mesh PCA principal directions (`principal_directions_kind=mesh_pca`)
- Algorithm id/version recorded on every `computed` field

Repeated execution yields identical payloads (tested).

---

## 10. Dental-axis handling

Clinical dental axes are a **separate** concept from mesh PCA.

- Engineering-reference frames from the artifact → frame `requires_review`; clinical axes `not_available`
- No genuine clinical axes on crown-only STL path → `not_available`
- Mesh PCA reported under `mesh_principal_directions` with an explicit non-clinical reason

---

## 11. Landmark handling

- Upstream landmarks (if present) → `requires_review`
- Official artifact / live TIN currently supply none → `not_available`
- Bounding-box corners / PCA extrema are **not** labeled as clinical landmarks

---

## 12. Occlusion handling

- Always `not_available` without bite/registration evidence
- Uses existing `unavailable_occlusion()` payload inside the truth value
- Capability `occlusion_readiness = not_available`
- UI preserves this state explicitly

---

## 13. Data-quality handling

Per-tooth / arch findings include (examples):

- Missing / empty / invalid mesh
- Missing arch or tooth_ref
- Fixture provenance
- Insufficient geometry for PCA

Findings are quality signals — **not** clinical diagnoses.

---

## 14. Provenance

Every case intelligence document binds:

- `case_id`, `job_id`, `input_hash`, `processing_mode`
- Per-tooth `source_mesh_path` / `source_mesh_sha256`
- Model name/version
- Algorithm + algorithm_version on computed fields
- `provenance` + `fixture`
- `generated_at`, `contract_version`

Persisted on the case store alongside WP-01 segmentation results.

---

## 15. Capability / readiness gates

Machine-readable (not a single score):

| Gate | Typical crown-only STL outcome |
|---|---|
| `identity_readiness` | `requires_review` |
| `geometry_readiness` | `computed` when meshes valid |
| `axis_readiness` | `not_available` |
| `occlusion_readiness` | `not_available` |
| `treatment_setup_readiness` | `requires_review` or `not_available` — **never verified by intelligence alone** |
| `validation_readiness` | `requires_review` when geometry exists |

Creating intelligence objects does **not** unlock Treatment Setup as clinically ready.

---

## 16. Frontend Analysis behavior

- Consumes `CaseDentalIntelligencePayload` via API
- Shows truth labels for overall intelligence, FDI, landmarks, clinical axes, roots, occlusion
- Capability readiness section visible
- Does not display fake FDI / landmarks / axes / occlusion / confidence / roots
- Mesh PCA explicitly described as non-clinical
- Minimum Analysis/API changes only — **no WP-03 viewport redesign**

---

## 17. Real-case evidence

| Item | Value |
|---|---|
| Official artifact | `official_real_case_stage2_verified_v1` |
| ZIP SHA-256 | `b0f57d45e19ec1c981964dcad1309570fdc96ec21052ada62050fa3ccb8621b2` |
| Extracted STLs | `.research/tmp/official_real_case_stage2_verified_v1/{upper,lower}.stl` |
| Path used for intelligence | Persisted segmentation tooth_instances reconstructed from the verified artifact (**test-only loader**); REAL_CASE live inference still blocked |
| Tooth instances processed | 28 (14 upper + 14 lower) |
| Resolved FDI | 0 |
| Unresolved identity | 28 |
| Arch assigned | 28 |
| Clinical axes available | 0 |
| Landmarks available | 0 |
| Occlusion | `not_available` |
| Roots | `not_available` (crown-only STL) |
| Geometry metrics | `computed` for all 28 instances with valid meshes |

Fixture geometry is used **only** as the official verified real-case evidence for non-GPU layers. It does not silently substitute into the production REAL_CASE inference path (WP-01 guarantee preserved).

---

## 18. Tests

| Suite | Coverage |
|---|---|
| `tests/python/test_wp02_dental_intelligence.py` | Real-artifact intelligence, determinism, no FDI invention, axes≠PCA, landmarks/occlusion NA, provenance/API, stale fail, fixture marking, readiness |
| `apps/web/src/wp02DentalIntelligence.test.ts` | Analysis truth-state rendering; treatment not unlocked |
| Existing WP-01 / P0–P8 | Must remain green |

---

## 19. Performance measurements

Measured on this machine against the official artifact (non-GPU geometry intelligence) via `test_measured_evidence_timings_recorded`:

| Metric | Observed |
|---|---|
| Intelligence generation (`timings_ms.total`) | **148.96 ms** |
| Per-tooth mean | **5.31 ms** |
| Per-tooth max | **10.96 ms** |
| Tooth instances | **28** |
| Resolved FDI | **0** |
| Unresolved identity | **28** |
| Arch assigned | **28** |
| Clinical axes available | **0** |
| Landmarks available | **0** |
| Occlusion | `not_available` |
| Live TIN GPU inference | **Not measured** — blocked (no torch/CUDA) |
---

## 20. Limitations

- No clinical FDI verification
- No clinical dental axes
- No landmarks
- No occlusion / bite registration
- No root/bone anatomy on STL
- `COMPUTED` geometry ≠ clinical validation
- Model FDI (when present) stays `requires_review`
- Treatment Setup not productized in this WP

---

## 21. Environment blockers

Identical to WP-01 for live inference:

- `.venv` has **no `torch`**
- No NVIDIA driver / CUDA runtime available for live ToothInstanceNet
- Checkpoint may exist on disk but cannot execute end-to-end here
- Non-GPU Dental Intelligence 2.0 layers **are** exercised against genuine artifact geometry

---

## 22. Explicit confirmation — WP-03 was NOT started

- No World-Class 3D Workspace redesign
- No viewport overhaul
- No Treatment Setup / Staging / Production CAD feature work beyond readiness **signals**
- No new research-model integration (3DTeethSAM not integrated)
- ToothInstanceNet not replaced
- GeometricValidationEngine authority not weakened

**STOP after WP-02.**
