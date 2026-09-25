# WP-04 — Tooth Interaction Engine

**Work package:** FIRST VERSION WP-04  
**Date:** 2026-09-25  
**Authoritative roadmap:** `AlignerStudio_PRODUCTION_MASTER_PLAN_v2.1.md`  
**Active First Version plan:** `Aligner_Studio_First_Version_World_Class_Plan.md`  
**Baselines:** `docs/FV01_PRODUCT_REALITY_AUDIT.md`, `docs/WP01_REAL_CLINICAL_DATA_PIPELINE.md`, `docs/WP02_DENTAL_INTELLIGENCE_2.md`, `docs/WP03_WORLD_CLASS_3D_WORKSPACE.md`  
**Scope:** Professional tooth interaction engine between World-Class 3D Workspace and future Treatment Setup.  
**Explicit stop:** **WP-05 and all later work packages were NOT started.**

---

## 1. Verdict

**PASS WITH BLOCKER** (same GPU/runtime blocker as WP-01–03: no live Torch/CUDA ToothInstanceNet in this environment).

- Real tooth instances from `official_real_case_stage2_verified_v1` are selectable and manipulable through stable semantic `tooth_ref`.
- Transforms are reversible state over immutable source geometry (P4 `rebuild_proposal` path).
- Lock / exclusion / undo / redo / provenance / plan versioning reuse and extend existing P4 — no second movement system.
- Constraint availability is honest (`unavailable` when limits are not configured).
- GeometricValidationEngine remains the validation authority after commit.
- No doctor-approved clinical state is exposed.
- No FDI fabrication, no clinical-axis invention, no Treatment Setup 2.0 / staging / IPR / attachments / occlusion / Production CAD.

This is **not** doctor-ready Treatment Setup and **not** WP-05.

---

## 2. Existing P4 capability audit

| Capability | Location | WP-04 decision |
|---|---|---|
| `ToothMovement` 6-DOF + lock/exclude | `domain/treatment_plan/setup.py` | Reused as transform payload |
| `DoctorMovementEdit` + edit history | `engines/planning/editing.py` | Reused; reason vocabulary extended |
| `apply_edit` / `apply_edit_and_recalculate` | `TreatmentEditingApplication` | Sole commit path |
| Source geometry integrity | `rebuild_proposal` from source states | Preserved |
| Lock gate | editing + FE `editing.ts` | Extended for exclude + restore reasons |
| Exclude gate | added/hardened in P4 apply | Pose changes blocked while excluded |
| Reset tooth / reset all | editing + API | Reused (`doctor_reset`) |
| Plan `version_id` / `plan_id` hashes | proposal rebuild | Preserved — no second versioning system |
| Undo/redo stacks | `App.tsx` | Extended with `system_restore` provenance |
| Gizmo draft | `StageViewer` TransformControls | Gated by `transformEnabled` / lock-exclude |
| Numeric draft | `InspectionPanel` | Gated by `canTransformTooth` |
| WP-03 selection | `tooth_ref` / `reviewToothKey` | Interaction target = selection identity |
| Validation | GeometricValidationEngine via recalculate | Triggered on apply; not bypassed |

**Decision:** Evolve P4 into a typed interaction engine adapter — do **not** create a parallel movement pipeline.

---

## 3. Architecture

```
WP-03 semantic selection (tooth_ref)
        ↓
Interaction state (phase, lock/exclude, draft transform, provenance reason)
        ↓
Draft manipulation (gizmo | numeric) — reversible, not baked into source
        ↓
Commit via P4 apply_edit_and_recalculate (reason + version + validation)
        ↓
Plan/version store + GeometricValidationEngine results
```

Frontend mirrors domain contracts in `apps/web/src/viewer/toothInteraction.ts`.  
Backend formalization: `domain/movement/interaction.py` + `engines/planning/interaction_engine.py`.

---

## 4. Data model

`ToothInteractionState` (domain + FE) includes:

- `case_id`, `tooth_ref`, `tooth_key`, arch, optional semantic label / FDI (never invented)
- `source_mesh_sha256` when available
- `base_transform`, `current_transform`, computed `delta_transform`
- `coordinate_space` (`world` | `engineering_local` | `clinical_local` | `unavailable`)
- `locked`, `excluded`, `phase`
- `constraint_availability`
- provenance / `version_id` / `transaction_id` / timestamps / validation status
- Explicit `clinically_approved: false`

Unavailable clinical fields are omitted or marked unavailable — never forced.

---

## 5. Transform model

Deterministic 6-DOF mapped 1:1 onto existing `ToothMovement`:

| Translation | Rotation / tipping |
|---|---|
| X, Y, Z (mm) | rotation, tip, torque, angulation (°) |
| intrusion / extrusion (mm) | preserved from existing schema |

Composition prefers draft → commit reconstruction from source, not cumulative mesh mutation.  
If clinically verified local axes are unavailable, interaction remains geometric/world or engineering-local and is labeled as such — mesh PCA is never treated as clinical dental axes.

---

## 6. Source / target separation

| Layer | Mutability |
|---|---|
| Source segmentation / source vertices | Immutable baseline |
| Target / interaction transform | Reversible state applied on rebuild |
| Viewport mesh object transform | Presentation of draft/current pose |

Reset restores the first recorded baseline movement for that tooth. Source meshes remain recoverable.

---

## 7. Interaction states

Phases: `idle` → `hovered` → `selected` → `actively_transforming`, plus `locked`, `excluded`, `review_required`, `unavailable`.

Priority: unavailable > locked > excluded > transforming > selected > hovered > idle.

Interaction phase is separate from WP-02 clinical truth state. Selection ≠ verification. Movable ≠ clinically allowed.

---

## 8. Manipulation behavior

Supported foundations:

- Translate / rotate gizmo (`StageViewer` TransformControls)
- Precise numeric inputs (`InspectionPanel`)
- Reset tooth / reset all (P4)
- Axis constraints via gizmo mode (translate vs rotate)
- Local/world: world/engineering frame when present; clinical local only if genuinely available (not invented)
- Gizmo drag grouped into one `InteractionTransaction` before Apply

Not implemented (out of scope): exaggerated animation, AI movement, staging UI, clinical “optimal movement” claims.

Workflow: Select → inspect → manipulate → Apply (commit + revalidate) → review → Undo/Redo.

---

## 9. Locking

- Locked teeth remain selectable/inspectable.
- Pose transforms blocked in FE (`canTransformTooth`, gizmo detach) and BE (`TreatmentEditingError`).
- Unlock (flag-only) remains allowed.
- Persistent via plan edit history / session store.
- Lock ≠ clinical approval.

---

## 10. Exclusion

- Excluded teeth remain visible and inspectable.
- Pose transforms blocked until included.
- Identity preserved; audited via edit history.
- Exclusion ≠ diagnosis or recommendation.

---

## 11. Constraints

Contract: `not_configured` | `configured` | `violating` | `unavailable`.

Existing P4 movement-limit assessment (`assess_movement_constraints`) is reused.  
When limits are absent, capability is **unavailable** — never invented thresholds.  
An unconstrained successful transform is **not** labeled clinically valid.

---

## 12. Undo / redo

- Client stacks store transform deltas (before/after `MovementSummary`), not duplicated meshes.
- Backend re-apply uses `system_restore` provenance.
- Gizmo updates group under one transaction until Apply.
- Case change / `clearRealCaseReview` clears undo/redo/transaction state.

---

## 13. Plan / version integration

Commits go through existing proposal `version_id` / `plan_id` hashing. Transform changes are part of the same plan revision stream. No incompatible second versioning system.

---

## 14. Provenance

Allowed reasons: `doctor_edit`, `doctor_reset`, `gizmo_edit`, `numeric_edit`, `reset`→normalized to `doctor_reset`, `system_restore`.

Unknown/AI-looking labels normalize to `doctor_edit` — never invent AI authorship.

Each meaningful edit records tooth identity, previous/new transform, timestamp, version, reason.

---

## 15. Validation integration

After Apply: existing `apply_edit_and_recalculate` runs staging rebuild + GeometricValidationEngine.  
WP-04 does not add a new validator and does not claim geometric success equals clinical safety.  
If validation is unavailable upstream, that status remains visible on the stage/tooth.

---

## 16. Real-case evidence

Artifact: `official_real_case_stage2_verified_v1` (persisted validated geometry; **no live GPU TIN claimed**).

| Metric | Measured value |
|---|---|
| Interactable teeth | **28** (14 upper + 14 lower) |
| Unique `tooth_ref` | **28** |
| FDI fabricated | **No** (all `fdi_number is None`) |
| Source mesh SHA (upper/lower prefixes) | `96e23a65e6a0` / `5cb38bd65cb2` |
| Selection→interaction state mapping | Pass (`tooth_ref` preserved) |
| Transform commit (P4 path) | Pass (`gizmo_edit`, version changed) |
| Source geometry intact after transform | **True** |
| Reset / `doctor_reset` | Pass (unit + P4 tests) |
| Lock blocks pose | Pass |
| Exclude blocks pose | Pass |
| Undo-style `system_restore` | Pass |
| Constraint availability (no limits) | `unavailable` |
| Validation present after commit | **True** |
| `clinically_approved` exposed | **Always false** |
| Fixture silent substitution in real evidence path | Artifact loader marks test_fixture; production inference not claimed |

---

## 17. Performance

Measured in this environment (not invented):

| Operation | Latency |
|---|---|
| Load upper artifact instances | 2234.50 ms |
| Load lower artifact instances | 1498.09 ms |
| Interaction state build | 0.037 ms |
| Commit transform + recalculate (synthetic P4 path) | 13.19 ms |
| Lock apply | 1.63 ms |
| Undo-style restore apply | 1.66 ms |

Notes:

- Transforms use movement state + object matrices; meshes are not duplicated per undo step.
- Headless WebGL selection/frame latency not measured here (same WP-03 environment limit).
- Memory after repeated transforms / case replacement not instrumented in this pass.

---

## 18. Tests

| Suite | Result |
|---|---|
| `tests/python/test_wp04_tooth_interaction.py` | 11 passed |
| `apps/web/src/wp04ToothInteraction.test.ts` | 10 passed |
| WP-01 + WP-02 + P4 editing + WP-04 combined | **42 passed** |
| FE WP-02 / WP-03 / editing / Inspection / toolbar + WP-04 | **26 passed** |

Coverage includes: identity, selection→transform, translate/rotate/6-DOF, reset, lock, exclude, undo/restore provenance, transaction grouping, source intact, constraint-unavailable honesty, no FDI fabrication, validation present after commit.

---

## 19. Limitations

- Not Treatment Setup 2.0; no staging/IPR/attachments/occlusion/production CAD.
- Clinical local dental axes remain unavailable for the official semantic-only artifact.
- Movement constraints typically unavailable unless limits are configured upstream.
- Live GPU TIN inference unavailable in this environment.
- Multi-tooth simultaneous gizmo not a productized multi-edit transaction (single semantic target per draft).
- Viewport WebGL performance not re-benchmarked beyond WP-03 foundations.

---

## 20. Environment blockers

- No `torch` / NVIDIA CUDA driver for live ToothInstanceNet inference (carried from WP-01–03).
- Real-case evidence uses genuine persisted validated artifact geometry only.

---

## 21. Explicit confirmation

**WP-05 and all later work packages were NOT started.**

Not started: Treatment Setup 2.0, Smart Staging, IPR, Attachments, Occlusion, Production CAD, new research model integrations.
