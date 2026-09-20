# OpenSourceOrtho Audit

**Status:** Research/reference audit only. No code copied or integrated.
**Audited repository:** [github.com/john-lawniczak/OpenSourceOrtho](https://github.com/john-lawniczak/OpenSourceOrtho)
(package name `opensource-ortho`, current version `1.4.0`, ~3 stars, 1 fork,
active — latest commit 2 months old as of this audit).
**Audit method:** Inspected the live repository's README, `docs/ARCHITECTURE.md`,
`docs/OPEN_SOURCE_REFERENCES.md`, `docs/segmentation-learned-backend.md`,
`pyproject.toml`, `LICENSE`, and the `orthoplan/model`, `orthoplan/segmentation`,
`orthoplan/evaluation/rules` directory listings via GitHub. Not cloned; no
source files were opened line-by-line beyond what GitHub's file/README
rendering exposed.

This is **not** the "OpenSourceOrtho" of ambiguous provenance — it is a real,
actively maintained, Apache-2.0 Python project explicitly designed as a
"safety-boundary-first clear-aligner treatment-planning research toolkit."

---

## 1. License

- **LICENSE file: Apache License 2.0** (confirmed by fetching the raw file).
- Copyright: "OpenSource Ortho contributors", 2026.
- Apache-2.0 is a permissive, commercial-use-friendly license: allows use,
  modification, sublicensing, and distribution (including in a closed-source
  or commercial product), requires preserving copyright/license notices and
  a NOTICE file if one exists, and includes an explicit patent grant.
- **No separate model-weight or dataset license applies to the core repo** —
  it ships no pretrained ML weights of its own (see §6).
- Verdict: **Apache-2.0 code is compatible with reuse in AlignerStudio**,
  including commercial use, subject to standard attribution/notice
  preservation. This must be re-verified against the exact commit/tag at the
  time of any actual integration (licenses can change between releases).

## 2. Existing Treatment-Plan Capabilities

Per `docs/ARCHITECTURE.md`, the "Simple Flow" is:

```
Upload STL → segment into tooth meshes → build TreatmentPlan (staged
ToothDelta values) → check stages against MovementCaps → build cumulative
StageProgressFrame objects → render in UI → deterministic rule checks (+
optional consent-gated advisory model review) → optional print-package export
```

Notable capabilities beyond a pure data model:

- **Plan generation** (`planning/generate.py`): resolves a target from, in
  priority order, authored movement → landmark-derived arch-form deviation
  target (with IPR/attachments/approximate collision bounds) → geometry-derived
  arch-form fit over segmented crowns → labeled educational template. Reuses
  one staging optimizer (`planning/optimizer.py`) rather than re-implementing
  staging per source.
- **Plan versioning**: `CaseStore`/`CaseRecord`/`PlanVersion` snapshots (full
  plan JSON + content hash + engine version + note), exposed via API and CLI.
- **Setup comparison**: side-by-side original/generated/edited/saved-version
  setups with "live restaging" that reruns target resolution, staging,
  collision/IPR checks, and timeline projection after edits, showing diffs
  rather than silently overwriting.
- **Handoff reports**: `orthoplan report PLAN.json` emits engine version,
  canonical plan hash, evaluation hash, findings, data-gap actions, timeline,
  progress frames, review metadata, report hash, optional HMAC-SHA256
  signature. No mesh bytes included.
- **Acquisition advisor**: computes which additional data (e.g. CBCT) would
  change which findings, without predicting what that data would show.
- Explicit non-goals stated in the repo itself: **not** a diagnosis engine,
  **not** a treatment-approval system, **not** a complete treatment-planning
  system, **not** a medical device.

## 3. Tooth Movement Representation

Per `docs/ARCHITECTURE.md` "Core Objects" and "How The Plan Moves Teeth":

- `ToothId` — canonical **FDI** identity in Phase 1; `arch` is _derived_ from
  the FDI quadrant (never stored separately, avoiding contradiction); mixed
  numbering systems (Universal/Palmer) are **rejected at plan creation**
  rather than silently normalized.
- `ToothDelta` — tooth identity, arch, **translation in millimeters**,
  **rotation in degrees**, a `CoordinateFrame`, and a movement source.
- `CoordinateFrame` — typed/named (not free-form string), declares axis
  semantics (`z` = occlusogingival, `x`/`y` = horizontal plane). Per-tooth
  mesiodistal/buccolingual axes are explicitly **unresolved at the global
  scan level** in Phase 1, so tip/torque/rotation are **not renderable**
  unless a trusted CBCT-derived anatomical frame exists for that tooth.
- Movement is **rigid transforms on segmented tooth objects**, never mesh
  deformation. Translation is a true, commutative vector sum (cumulative
  translation is geometrically correct). Rotation (tip/torque/rotation as
  summed Euler components) is explicitly **not a composable rigid rotation**
  — the project tracks a `rotation_renderable` flag and refuses to build a
  rotation matrix from a non-renderable pose. This is a deliberate,
  documented honesty boundary, not an oversight.
- `MovementCaps` — user-configurable per-stage caps (`AxisCaps`): default
  linear 0.25 mm/stage, angular (tip/torque) 1.0°/stage, rotation 2.0°/stage,
  intrusion/extrusion 0.10 mm/stage. Explicitly labeled as **"literature/vendor
  heuristics, not medical clearance"** and gated on confirmed scan units.
  `per_tooth_overrides` reserved for future tooth-class-specific caps.

## 4. Staging

- `Stage` = one aligner-style step containing a list of per-tooth
  `ToothDelta` values.
- `StageProgressFrame` = cumulative tooth positions at a stage, carrying
  `rotation_renderable` and a crown-centroid pivot label, plus attached data
  gaps for the UI. Single source of truth: the UI never recomputes movement
  independently — it renders exactly what `planning/transforms.py` /
  `build_stage_progress_frames()` produce.
- Staging respects `MovementCaps`, `fixed-teeth`/`exclusions`, and a
  `targets-reached` regression check (staged cumulative movement must
  actually reach the requested target — guards against silent staging bugs).
- Timeline (`planning/timeline.py`) is an **arithmetic projection only**
  (stage count × `wear_interval_days`, default 14) explicitly caveated as
  excluding refinements, compliance variation, and pauses — not an outcome
  estimate.

## 5. Collision / Proximity Validation

- `orthoplan/evaluation/rules/collisions.py` and `contact_geometry.py` —
  deterministic crown-proximity / collision checks over segmented crown
  geometry (approximate collision bounds, per the architecture doc's
  description of the landmark-derived plan path).
- `collisions-checked` is reported as an **informational** check (not a gate)
  — it explicitly reports when the overlap check is "vacuous" (no segmented
  teeth exist), rather than silently passing.
- Root/bone-aware proximity is a **separate, higher tier**: `root_bone.py`
  and `root_apex.py` implement root-proximity, cortical-boundary proximity,
  and a geometric root-apex sweep estimate (`root_length * sin(angulation)`
  about the crown-centroid pivot) — but only when CBCT-derived anatomy has
  passed a numeric registration-quality gate (PASS/MARGINAL/FAIL on RMSE,
  fitness, inlier ratio) and human review. Everything else reports "cannot
  assess" rather than guessing.

## 6. IPR (Interproximal Reduction)

- IPR is referenced as part of the **landmark-derived plan path**
  (`planning/landmark_plan.py`): "a space analysis that budgets IPR, adds
  attachments, and checks crown collisions." IPR is treated as a plan
  input/metadata field authored through direct 3D controls
  (`IPR/spacing metadata`), not an independently documented deterministic
  algorithm module of its own that we could isolate cleanly. No dedicated
  `ipr.py` rule file was observed in the `evaluation/rules` listing — it
  appears integrated into `plan_checks.py` / `clinical_controls.py` /
  `landmark_plan.py` rather than a standalone engine.

## 7. Attachments

- Same status as IPR: attachments are a **plan metadata/authoring concept**
  (direct 3D controls mention "attachment/IPR/spacing metadata" and
  "attachment/cut placement"), consumed by the landmark-derived plan
  generator and clinical-controls rules, not a separate geometric attachment-
  placement engine with its own algorithm we could lift out.

## 8. Case / Mesh Pipeline

- STL upload is **metadata-only in Phase 1** (`orthoplan/io/stl_import.py`):
  mesh bytes are never stored in the serialized plan; only redacted metadata
  and an optional relative reference are kept. Absolute paths/directory
  structure are stripped (patient-name leakage risk). STL carries no units
  → units default to `unverified` and must be user-confirmed before
  movement-cap evaluation runs. Bounding-box sanity check warns on
  implausible scale but never infers units.
- **Local mesh workspace**: plan JSON never stores mesh bytes; real per-tooth
  STL meshes are registered locally (`orthoplan register-mesh`) and served
  only by asset id (`/api/mesh/<mesh_asset_id>`) from a local workspace the
  dev server controls. The UI falls back to schematic proxy teeth when no
  registered mesh is available.
- **Case/version store**: `CaseStore` of `CaseRecord`s with ordered
  `PlanVersion` snapshots, defaulting to a local `.orthoplan-cases.json` file
  (overridable via `ORTHOPLAN_CASE_STORE`).
- **CBCT/DICOM tier** (optional, `dicom` extra via `pydicom`): local
  record ingestion with PHI-aware metadata handling, explicit STL-to-CBCT
  registration with quality metrics, reviewable derived anatomy (roots,
  alveolar bone, tooth axes), deterministic root/bone-aware findings that
  **fail closed** when registration/segmentation quality is insufficient.
  Raw DICOM volume bytes are never committed to their sample data.

## 9. Segmentation

- **Default backend**: a **dependency-free heuristic** (`segmentation/
heuristic.py`, `hybrid.py`, `arch_profile.py`) — a 1-D valley/graph-cut-style
  approach using arch position, crown-height valleys, curvature, and
  face-normal changes. Self-reported as functionally correct on tooth
  **count** and **boundary labels** (14/14 on bundled real test scans) but
  geometrically rough: "per-tooth meshes are rough vertical wedge slabs" —
  described by the maintainer as a correctness _floor_, not
  crown-accurate geometry.
- **Optional CBCT-informed segmentation**: when a plan carries trusted,
  gate-passing registered CBCT anatomy, volume-derived interproximal
  boundary priors _bias_ (never replace) the heuristic cut placement, and
  cut/prior agreement calibrates per-tooth confidence.
- **Learned-model seam (no shipped model)**: `segmentation/learned.py`
  implements the same `segment(...)` contract via **ONNX Runtime only**
  (never PyTorch/torch at runtime), selected automatically by
  `load_local_segmenter()` behind an install/weights-availability check;
  heuristic remains the always-on fallback so a broken/missing optional
  backend can never take down segmentation. Weights are **user-supplied**
  via `$OPENSOURCE_ORTHO_SEG_WEIGHTS` and are **never committed** to the repo.
  This seam is explicitly the intended integration point for an external
  model — see §11.
- **Quality gating**: `segmentation/quality.py` separates "reviewable" vs.
  "production candidate" segmentations using tooth-count, crown-compactness,
  and confidence metrics; the shipped heuristic clears "reviewable" but is
  intentionally blocked from being a "production candidate."
- Everything downstream (API, mesh export, viewer) consumes a single
  `list[ToothSegment]` contract (`tooth_value`, `triangles`, `centroid`,
  `confidence`) regardless of which backend produced it — a clean seam.

## 10. Export

- `TreatmentSettings.print_export` records export intent: format
  (`stl`/`3mf`), delivery email, model/thermoforming material,
  post-processing notes, and a required safety acknowledgement.
- `orthoplan print-package PLAN.json --out DIR` generates **stage proxy STL
  files** (sized from segmented mesh bounds when available, otherwise
  explicitly labeled schematic proxy geometry), a manifest (engine version,
  canonical plan hash, stage-frame hash, per-artifact SHA-256 hashes, byte
  sizes, blockers, geometry-source metadata), an optional deterministic zip,
  and an optional `.eml` email draft.
- Explicitly documented as **not** a certification, warranty, clearance, or
  authorization to physically use an appliance. The stated next
  print-geometry phase is packaging _actual_ per-tooth vertices instead of
  bounded proxy solids — i.e. today's STL export is schematic/proxy, not
  true per-tooth geometry, unless a mesh has been registered locally.

## 11. Where ToothGroupNetwork / MeshSegNet Could Replace/Improve Segmentation

The project's own `docs/segmentation-learned-backend.md` already did this
analysis (dated "checked June 2026") and reached conclusions consistent with
our [REUSE_MATRIX.md](../REUSE_MATRIX.md):

- **MeshSegNet** (`Tai-Hsien/MeshSegNet`): **code is MIT**, and the repo
  ships pretrained PyTorch weights (upper/lower). But:
  - No ONNX export provided — exportable but "fiddly" (GLM layers consume
    mesh-adjacency matrices as extra inputs).
  - **Weights' license is undocumented** — trained on a private clinical
    IOS dataset (Lian et al.); redistribution/commercial terms for the
    _weights_ are unstated and must be cleared before shipping them.
    Recommended mitigation (same as our repo's own policy): treat weights as
    **user-supplied, never redistributed**.
  - Non-trivial preprocessing required: decimate mesh to ≤10k cells, build
    15-dim per-cell features (9 vertex coords + 3 normal + 3 relative
    position), 15 classes (14 teeth + gingiva) → map to FDI.
- **ToothGroupNetwork** (`limhoyeon/ToothGroupNetwork`): **no LICENSE file
  in the repository** (confirmed — a direct fetch of `LICENSE` returns
  404). Under default copyright, all rights are reserved by the author;
  **this repo cannot be reused, redistributed, or relied on for commercial
  training/inference without explicit permission from the author**, even
  though the code is publicly visible on GitHub. It should remain
  **reference-only** in our [REUSE_MATRIX.md](../REUSE_MATRIX.md) until an
  explicit license is added upstream or granted directly.
  - Additionally, its primary training dataset (3DTeethSeg'22 / Teeth3DS+)
    is **CC BY-NC-ND 4.0** (non-commercial, no-derivatives) per
    OpenSourceOrtho's own audit — a model trained on it cannot be used in a
    commercially reusable product regardless of the code's own license
    status.
- **Recommended integration seam for AlignerStudio**: mirror
  OpenSourceOrtho's approach exactly — an ONNX-Runtime-only inference
  adapter behind our existing `engines/segmentation.SegmentationEngine`
  interface, with weights resolved from a user-supplied path/env var and
  **never committed to the repo**, and the current
  `PlaceholderSegmentationEngine` retained as the always-available fallback.
  This defers the model-weight licensing question entirely to the
  deployer/user rather than to AlignerStudio's own repository, exactly as
  documented in [REUSE_MATRIX.md](../REUSE_MATRIX.md) row for
  `adapters/meshsegnet`.

## 12. Data Models (Summary)

| Model                                                                                 | Purpose                                                                                                                      |
| ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `TreatmentPlan`                                                                       | plan id/title, numbering system (FDI/Universal/Palmer), `DataAvailability` manifest, staged movement list, movement settings |
| `Stage`                                                                               | one aligner-style step; list of `ToothDelta`                                                                                 |
| `ToothDelta`                                                                          | tooth identity, arch, translation (mm), rotation (deg), `CoordinateFrame`, movement source                                   |
| `ToothId`                                                                             | canonical FDI identity; arch derived, never stored separately                                                                |
| `CoordinateFrame`                                                                     | typed/named; axis semantics; explicit "not resolved at global scan level" flag                                               |
| `MovementCaps` / `AxisCaps`                                                           | per-stage movement guardrails, not medical clearance                                                                         |
| `StageProgressFrame`                                                                  | cumulative tooth positions + `rotation_renderable` + data gaps                                                               |
| `DataAvailability`                                                                    | tracks which modalities/records exist for a case                                                                             |
| `CaseRecord` / `PlanVersion`                                                          | versioned plan snapshots with content hash + engine version                                                                  |
| `ToothSegment`                                                                        | segmentation contract: `tooth_value`, `triangles`, `centroid`, `confidence`                                                  |
| Registration/anatomy models (`registration.py`, `registration_gate.py`, `anatomy.py`) | CBCT-to-STL registration quality gating and derived anatomy, all provenance-tagged                                           |

## 13. Dependencies

From `pyproject.toml` (core + optional extras):

| Dependency                         | Scope                   | Notes                                                                             |
| ---------------------------------- | ----------------------- | --------------------------------------------------------------------------------- |
| `pydantic>=2.7`                    | core                    | plan/data models                                                                  |
| `typing-extensions>=4.12`          | core                    | typing                                                                            |
| `pytest>=8.0`, `ruff>=0.6`         | dev                     | test/lint                                                                         |
| `openai>=1.0`                      | `providers` extra       | optional advisory model provider                                                  |
| `trimesh>=4.0`                     | `mesh` extra            | STL/OBJ loading, transforms, bounds — **same library AlignerStudio already uses** |
| `open3d>=0.18`                     | `mesh-processing` extra | optional mesh processing — **same library planned for AlignerStudio**             |
| `pydicom>=2.4`                     | `dicom` extra           | local CBCT/DICOM metadata only, never pixel/volume bytes                          |
| `onnxruntime>=1.17`, `numpy>=1.24` | `ml-seg` extra          | learned segmentation backend inference only — **no torch at runtime**             |
| `playwright>=1.40`                 | `e2e` extra             | browser E2E tests                                                                 |

Notably **no PyTorch dependency at runtime anywhere in the core or optional
extras** — training tooling for any learned backend is explicitly kept
outside the shipped package. This is directly aligned with AlignerStudio's
own "deterministic algorithms wherever possible, ML behind a swappable
adapter" principle.

## 14. Licensing / Commercial-Use Constraints Summary

| Component                            | License                        | Commercial use?                                                      |
| ------------------------------------ | ------------------------------ | -------------------------------------------------------------------- |
| OpenSourceOrtho core code            | Apache-2.0                     | Yes, with attribution/notice preservation                            |
| `trimesh`, `open3d`, `pydicom`       | MIT / MIT / MIT                | Yes                                                                  |
| `three.js` (vendored in their `ui/`) | MIT                            | Yes                                                                  |
| MeshSegNet **code**                  | MIT                            | Yes (code only)                                                      |
| MeshSegNet **pretrained weights**    | Undocumented                   | **No — must be cleared before any use**, treat as user-supplied only |
| ToothGroupNetwork **code**           | **None (all rights reserved)** | **No — reference-only until explicit license granted**               |
| Teeth3DS+ / 3DTeethSeg'22 dataset    | CC BY-NC-ND 4.0                | **No — non-commercial, no-derivatives**                              |
| BlueSkyPlan                          | Proprietary (EULA required)    | Not open source — reference only                                     |
