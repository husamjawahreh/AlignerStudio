# WP-05 — Treatment Setup 2.0

**Work package:** FIRST VERSION WP-05  
**Date:** 2026-09-25  
**Authoritative roadmap:** `AlignerStudio_PRODUCTION_MASTER_PLAN_v2.1.md`  
**Active First Version plan:** `Aligner_Studio_First_Version_World_Class_Plan.md`  
**Baselines:** FV-01, WP-01, WP-02, WP-03, WP-04  
**Scope:** Persistent, reversible orthodontic treatment-planning layer (source / current / target + versioning).  
**Explicit stop:** **WP-06 and all later work packages were NOT started.**

---

## 1. Verdict

**PASS WITH BLOCKER** (same GPU/runtime blocker as WP-01–04: no live Torch/CUDA ToothInstanceNet).

- Treatment Setup 2.0 is a real persistent planning contract (`treatment_setup_2.0`) over P4 proposals.
- SOURCE / CURRENT / TARGET are explicitly separated; source geometry remains immutable.
- Target edits reuse WP-04 / P4 apply → restage → GeometricValidationEngine.
- Saved versions are immutable snapshots with `parent_version_id` lineage.
- Current vs target and version A vs B comparison are geometric only — no clinical ranking/score/approval.
- Constraints and readiness gates are honest (`unavailable` / `not_available` when unsupported).
- No FDI fabrication, no ideal positions invented, no clinically approved state.

This is **not** Smart Staging, IPR, Attachments, Occlusion, or Production CAD.

---

## 2. Existing P4 / WP-04 audit

| Capability | Reuse decision |
|---|---|
| `TreatmentPlanProposal` + hashed `plan_id`/`version_id` | Reused as content-addressed working state |
| `TreatmentEditingApplication` | Sole target-edit path (+ batch `apply_edits`) |
| WP-04 interaction / provenance reasons | Reused for target commits |
| Session store + pickle checkpoint | Extended with `version_history` |
| GeometricValidationEngine on edit | Preserved |
| Review bundle stages / ghost / undo | Preserved; enriched with setup contract |
| Plan version list / compare / restore | **Added** (was missing) |
| `parent_version_id` | **Added** |
| Formal SOURCE/CURRENT/TARGET DTO | **Added** |

---

## 3. Treatment state architecture

```
SOURCE  — immutable processed geometry (setup.source_states)
CURRENT — patient layer; equals SOURCE in First Version (no progress scan)
TARGET  — doctor/planner transforms over source (setup.target_states)
VERSION — immutable snapshots of proposal + staging + validation
```

Stable lineage id: `setup:{case_id}` (`setup_plan_id`).  
Working content hashes remain P4 `plan_id` / `version_id`.

---

## 4. Source / current / target separation

- Edits change **target** transforms only.
- Rebuild always transforms from **source** vertices (`rebuild_proposal`).
- CURRENT is documented as equal to SOURCE until progress scans exist.
- Target ghost uses final stage (WP-03 overlay) — no second viewer.

---

## 5. Target tooth model

`ToothTargetState` carries: case_id, tooth_ref/key, arch, semantic identity, source/current/target transforms, delta, coordinate space, lock/exclude, constraint availability, validation, limitations, `clinically_approved: false`.

Unavailable clinical fields are omitted or null — never fabricated.

---

## 6. Versioning

- Baseline snapshot seeded on session create.
- `save_version` appends immutable snapshot (content-addressed; duplicates skipped).
- Later edits create new working `version_id`; they do **not** mutate saved snapshots.
- `restore_version` loads snapshot into working state; sets `parent_version_id`.
- `compare_versions` returns geometric deltas only (`clinical_ranking: null`).

API:

- `GET/POST /cases/{id}/treatment/versions`
- `POST .../versions/restore`
- `POST .../versions/compare`
- `POST .../edits/batch` (multi-tooth)

---

## 7. Target editing

Workflow: select (WP-03) → inspect → WP-04 draft → Apply (P4) → validate → optional Save version.

Multi-tooth: `apply_edits` / batch API — one rebuild, per-tooth provenance. Lock/exclude still gate pose changes. Absolute targets (no cumulative double-application).

---

## 8. Constraints

Reuses WP-04 `ConstraintAvailability`. When limits absent → `unavailable`. Never invents thresholds. Unconstrained geometric success ≠ clinical acceptability.

---

## 9. Lock / exclusion

WP-04 / P4 gates preserved for target transforms. Inspectable; not clinical approval.

---

## 10. Validation integration

Every session edit/reset/recalculate/batch path still runs GeometricValidationEngine. Validation status/snapshots stored on versions. No replacement engine. Execution ≠ safety claim.

---

## 11. Readiness / capability gates

Machine-readable: real_geometry, identity, arch, transform, constraint, validation, occlusion, clinical_axes.  
Never an overall AI score. `unsupported_features_unlocked: false`. Occlusion/clinical axes remain `not_available`.

---

## 12. Comparison

- Current vs target in `treatmentSetup.current_vs_target`
- Version A vs B via compare API
- Changed/unchanged teeth + geometric deltas
- No ranking / optimality claims

---

## 13. Provenance

Edit reasons: `doctor_edit`, `gizmo_edit`, `numeric_edit`, `doctor_reset`, `system_restore`.  
Version author_source: `doctor` | `deterministic_planner` | honest generic when identity unavailable.  
Audit trail preserved in `editHistory` + version metas.

---

## 14. Frontend UX

`TreatmentSetupPanel` / inspector distinguish SOURCE · CURRENT · TARGET · VERSION.  
Save / restore / compare wired in App. Target ghost + refinement editing unchanged (WP-03/04). Staging/IPR/attachments not newly enabled.

---

## 15. Real-case evidence

Official artifact identity checks: **28** teeth, unique `tooth_ref`, **no FDI**.  
Measured setup lifecycle (engineering session path using same P4/validation engines):

| Evidence | Result |
|---|---|
| Setup creation | Pass (baseline version seeded) |
| Target edit | Pass (`numeric_edit`) |
| Target teeth with non-identity transform after edit | **2** |
| Validation after edit | `warning` (engine ran) |
| Version save | Pass (2 versions) |
| Version restore | Pass (tx restored to 0.35) |
| Version compare | changed **1**, unchanged **15** |
| Source geometry intact | **True** |
| Reopen persistence (session checkpoint) | **True** (2 versions) |
| `clinically_approved` | **False** |
| Constraints | `unavailable` |
| Contract | `treatment_setup_2.0` |

Live GPU TIN not claimed.

---

## 16. Performance

Measured (not invented):

| Operation | Latency |
|---|---|
| Create setup (+ staging/validation/intelligence) | 2571.61 ms |
| Target edit + recalculate | 3070.68 ms |
| Save version | 10.63 ms |
| Restore version | 1863.31 ms |
| Compare versions | 0.22 ms |

---

## 17. Tests

| Suite | Result |
|---|---|
| `tests/python/test_wp05_treatment_setup.py` | **10 passed** |
| `apps/web/src/wp05TreatmentSetup.test.ts` | **2 passed** |
| FE WP-02/03/04 + WP-05 | **22 passed** |
| Combined WP-01/02/04/05 + P4 editing | run in verification |

---

## 18. Limitations

- CURRENT equals SOURCE (no progress-scan layer yet).
- Clinical axes / occlusion readiness remain unavailable.
- Movement constraints typically unavailable without configured limits.
- Not Smart Staging / IPR / Attachments / Occlusion / Production CAD.
- Multi-tooth gizmo UX still primarily single-draft; batch API exists for safe multi commits.

---

## 19. Environment blockers

- No Torch/CUDA for live ToothInstanceNet (carried from WP-01–04).
- Real-case geometry evidence uses persisted validated artifact.

---

## 20. Explicit confirmation

**WP-06 and all later work packages were NOT started.**

Not started: Smart Staging, IPR productization, Attachments productization, Occlusion, Production CAD, new research model integrations.
