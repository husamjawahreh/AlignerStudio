# WP-06 — Smart Staging Engine

**Work package:** FIRST VERSION WP-06  
**Date:** 2026-09-25  
**Authoritative roadmap:** `AlignerStudio_PRODUCTION_MASTER_PLAN_v2.1.md`  
**Active First Version plan:** `Aligner_Studio_First_Version_World_Class_Plan.md`  
**Baselines:** FV-01, WP-01 … WP-05  
**Scope:** Deterministic, auditable staging from Treatment Setup 2.0 targets.  
**Explicit stop:** **WP-07 and all later work packages were NOT started.**

---

## 1. Verdict

**PASS WITH BLOCKER** (same GPU/runtime blocker as WP-01–05: no live Torch/CUDA ToothInstanceNet).

- Smart Staging wraps Phase-6 linear staging with setup-version binding, truth states, readiness, and stale detection.
- Final stage reproduces the selected Treatment Setup target within technical numerical tolerance (`1e-9`).
- Staging is versionable/immutable; regenerate is explicit.
- Constraints/occlusion/axes honesty preserved; never clinically optimal/approved.
- Real-case identity checks: 28 teeth, no FDI fabrication.

This is a **computational staging proposal**, not an autonomous clinical planner.

---

## 2. Existing staging audit

| Capability | Decision |
|---|---|
| `TreatmentStagingEngine` linear interpolation | **Reused** as sole interpolator |
| Stage 0 = source, final = target | **Preserved** |
| `resolve_dynamic_stage_count` magnitude heuristic | **Reused** (engineering only) |
| Coupled restage on edit (P4/WP-05) | **Preserved** as default `restage=True` |
| Setup version snapshots carrying staging cargo | **Preserved** |
| Independent staging plan versions / stale / truth | **Added (WP-06)** |
| Collision-aware / clinical timing sequencing | **Not claimed / not invented** |

---

## 3. Architecture

```
Treatment Setup target (WP-05 version_id)
        ↓
TreatmentStagingEngine (linear progress interpolation)
        ↓
SmartStagingPlan (bind + truth + readiness + tolerance check)
        ↓
GeometricValidationEngine (per composed session)
        ↓
review_bundle.smartStaging + staging versions
```

---

## 4. Staging data model

`SmartStagingPlan` / `SmartStagingVersionMeta`:

- `staging_plan_id` = `staging:{case_id}`
- `staging_version_id` = Phase-6 `staging_id` (content hash)
- `source_setup_version_id` (binding)
- `parent_staging_version_id`
- algorithm name/version, configuration, input hash
- stage_count, affected_tooth_count
- truth_state, freshness, limitations
- `clinically_approved: false`, `clinically_optimal: false`

---

## 5. Stage representation

- Stage 0: baseline/source (honest; equals CURRENT when no progress scan)
- Intermediate: linear progress `k/(n-1)` on movements + vertices
- Final: exact Treatment Setup target
- Prefer transform/state; Phase-6 already avoids unnecessary vertex copies when unchanged

---

## 6. Algorithm

**Name:** `linear_progress_interpolation`  
**Version:** `wp06-smart-staging-1`

Deterministic linear DOF scale + vertex lerp. Dynamic stage count from movement magnitude (macro/micro engineering steps). Documented as computational — **not clinically optimized**.

---

## 7. Movement decomposition

`T_k = progress_k * T_target` with `progress = k/(n-1)`.  
Final composition verified with **technical** tolerance `1e-9` (not a clinical tolerance).

---

## 8. Multi-tooth behavior

All teeth staged together with preserved `tooth_ref` / arch / per-tooth movement. Excluded teeth remain identity (source vertices). Locked teeth are not newly edited; existing target pose still stages honestly.

---

## 9. Constraints

`ConstraintAvailability` from WP-04/05. Absent limits → readiness `unavailable`. No invented biological thresholds.

---

## 10. Validation

Session regenerate/edit path still runs GeometricValidationEngine. Status attached to smart staging meta. Execution ≠ “stage is safe”.

---

## 11. Truth states

Generated proposals: `requires_review` (never auto-`verified`). Unavailable when no stages. Doctor review always required.

---

## 12. Doctor review / editing

Inspect stages via existing StageViewer/timeline. Explicit regenerate + save staging version. Stage reorder/per-tooth reassignment deferred as extension point (not faked). Manual edits remain auditable through setup edit provenance + staging version history.

---

## 13. Versioning

- Seed staging version on session compose
- Append staging snapshots on restage/regenerate
- Save staging version freezes current plan (rejects if stale)
- Restore staging version loads immutable snapshot and evaluates freshness vs current setup

---

## 14. Stale-state handling

If `source_setup_version_id != proposal.version_id` → `freshness=stale`.  
Produced by `apply_edit(..., restage=False)`. UI/API expose current/stale/unavailable. Regenerate is explicit — no silent rebase.

---

## 15. Provenance

Records case, setup version, staging version, algorithm, configuration, input hash, timestamp, truth, limitations, author_source (`doctor` / `system` / `deterministic_planner` / `system_restore`).

---

## 16. Frontend integration

`StagingPanel` shows freshness, truth, final=target, algorithm, stale warning, Generate/Regenerate, Save staging version. Stage timeline/playback unchanged (discrete stages; not clinical simulation).

API:

- `POST /treatment/staging/regenerate`
- `GET/POST /treatment/staging/versions`
- `POST /treatment/staging/versions/restore`
- `restage` flag on treatment edits

---

## 17. Real-case evidence

Official artifact: **28** teeth, unique `tooth_ref`, **no FDI**.  
Measured setup lifecycle (engineering session; same engines as real-case path):

| Evidence | Result |
|---|---|
| Staging create | Pass (3 stages) |
| Final equals target | **True** (err 0.0) |
| Truth state | `requires_review` |
| Affected teeth | **2** |
| Coupled edit freshness | `current` |
| Stale after `restage=False` | **stale** |
| Regenerate | Pass → `current`, final_ok True |
| Source intact | **True** |
| Validation | `warning` (engine ran) |
| Save staging versions | **2** |
| Reopen | **True** (3 stages) |
| clinically_optimal | **False** |

Test target transforms are doctor-edit pathway movements — not clinical recommendations.

---

## 18. Performance

| Operation | Latency |
|---|---|
| Create setup+staging+validation | 2852.02 ms |
| Coupled edit+restage | 1877.78 ms |
| Save staging version | 10.28 ms |
| Explicit regenerate | 1821.89 ms |

---

## 19. Tests

| Suite | Result |
|---|---|
| `tests/python/test_wp06_smart_staging.py` | **10 passed** |
| WP-04+05+06+Phase6 staging+P4 editing | **50 passed** |
| FE WP-04/05 + StageTimeline | **13 passed** |

---

## 20. Limitations

- Linear computational staging only (no collision-aware sequencing).
- No clinical movement limits invented.
- Stage reorder UI not productized.
- CURRENT baseline equals SOURCE without progress scans.
- Playback is discrete stage scrubbing, not biomechanical simulation.

---

## 21. Environment blockers

- No Torch/CUDA live ToothInstanceNet (carried from WP-01–05).

---

## 22. Explicit confirmation

**WP-07 and all later work packages were NOT started.**

Not started: IPR, Attachments, Occlusion, Production CAD, WP-11 redesign, new research models.
