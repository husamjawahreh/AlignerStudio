# Reuse Decision: OpenSourceOrtho, MeshSegNet, ToothGroupNetwork

**Status:** Decision record plus Phase 3 adapter decision. No external source
code or model weights have been copied into this repository.
See [OPENSOURCE_ORTHO_AUDIT.md](OPENSOURCE_ORTHO_AUDIT.md) for the full
audit this decision is based on.

## Decision

| Source                                                                   | Decision                                                                                                               | Rationale                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| ------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **OpenSourceOrtho** (Apache-2.0)                                         | **Reference architecture + selective, re-implemented concepts.** Do **not** vendor/import its Python package directly. | License permits reuse, but our `domain/`/`engines/` layering, `DataProvenance` model, and clinical-boundary documentation process are already independently designed and stricter in some respects (e.g. our fixture-labeling contract). Re-implementing their proven _concepts_ in our own types keeps us in full control of the domain model and avoids taking on their whole dependency/CLI/UI surface (which includes a browser UI, mobile scaffolding, AI-chat connectors, and CBCT/DICOM tooling far beyond our Phase 1/2 scope). |
| **MeshSegNet** (`Tai-Hsien/MeshSegNet`)                                  | **Reference only for now. Code (MIT) is reusable; pretrained weights are NOT cleared for reuse.**                      | Code license is fine, but the shipped weights have no stated license and were trained on a private clinical dataset. Any future adapter must require the deployer to supply their own weights (never redistribute weights in our repo), mirroring OpenSourceOrtho's own policy.                                                                                                                                                                                                                                                         |
| **ToothGroupNetwork** (`limhoyeon/ToothGroupNetwork`)                    | **Reference only. Do not integrate, train on, or redistribute.**                                                       | No LICENSE file exists in the repository (confirmed 404 on `LICENSE`) — default copyright applies, meaning no reuse rights are granted. Its primary training dataset (Teeth3DS+/3DTeethSeg'22) is CC BY-NC-ND 4.0, which independently blocks commercial use even if code permission were later granted.                                                                                                                                                                                                                                |
| **Teeth3DS+ / 3DTeethSeg'22 dataset**                                    | **Do not use**, for training or evaluation in any commercially-oriented build.                                         | CC BY-NC-ND 4.0 is non-commercial and no-derivatives.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| **Open3D, trimesh, pydicom, three.js** (all used by OpenSourceOrtho too) | **Already approved** in our [REUSE_MATRIX.md](../REUSE_MATRIX.md) as direct dependencies.                              | MIT-licensed utility/geometry libraries, not clinical algorithms; no adapter needed.                                                                                                                                                                                                                                                                                                                                                                                                                                                    |

## What We Can Reuse (Concepts, Not Code)

These are **design patterns to re-implement independently** in our own
`domain`/`engines` packages — never literal code copies:

1. **Fail-closed rotation honesty** — track a `rotation_renderable`-style
   flag rather than fabricating a rotation matrix when the anatomical frame
   isn't resolved. Directly reusable as a design pattern in
   `domain/treatment_plan` once we add rotation.
2. **`ToothId`/arch-derivation invariant** — deriving `arch` from FDI
   quadrant rather than storing it independently (prevents contradiction).
   Our `domain/tooth/models.py` already does exactly this via the `arch`
   property — no change needed, just confirms our existing design is sound.
3. **Movement caps as configurable, explicitly non-clinical guardrails** —
   matches our own `CLINICAL_BOUNDARIES.md` philosophy; we should adopt
   similarly explicit "not medical clearance" language when we add staging
   caps in a later phase.
4. **Segmentation backend seam** (`load_local_segmenter()` pattern) — informs
   our Phase 3 ONNX adapter boundary. AlignerStudio intentionally tightens
   the fallback rule: the external adapter is optional at installation time,
   but a missing model raises an explicit error in the production path; the
   legacy fixture is not silently selected. ONNX Runtime only, no torch at
   runtime, weights via explicit local path, never committed.
5. **Plan versioning via content-hashed snapshots** — a `CaseRecord` holding
   ordered, hashed `PlanVersion`s is a clean pattern worth adopting when we
   build "Modify → Recalculate" in a later phase.
6. **Handoff report hashing** (engine version + plan hash + evaluation hash
   - optional HMAC signature) — a good reference for our future `export`
     phase, to make exported plans independently verifiable.
7. **Deterministic checks return a verdict enum (`CONSISTENT`/`ISSUES`),
   never "safe"/"approved"** — reinforces our existing `DataProvenance` rule
   that generated output is never silently upgraded to clinically reviewed.

## What We Should Replace / Not Adopt As-Is

- **Their whole application surface** (browser UI, mobile scaffolding, AI
  chat connectors, CLI) — out of scope; AlignerStudio has its own
  React/Vite/Three.js frontend and FastAPI backend already scaffolded.
- **IPR/attachments as loosely-typed plan metadata** — their own audit shows
  these are folded into `landmark_plan.py`/`clinical_controls.py` rather than
  standalone modules. When we build IPR/attachments (later phase), we should
  give them **first-class domain models** in `domain/treatment_plan` (or a
  new `domain/movement` module) rather than following their metadata-bag
  pattern, to keep with our own "no giant files, strong typing" rules.
- **Geometric heuristic segmentation quality** — their own docs
  self-report it produces "rough vertical wedge slabs," not
  crown-accurate geometry. Not worth porting as our real segmentation engine;
  better to go straight for a properly licensed learned-model adapter when
  the time comes (see Recommended Integration Path).

## What Is Missing (Neither We Nor OpenSourceOrtho Have It Cleanly)

1. **A commercially-reusable, license-clear pretrained tooth-segmentation
   model.** Neither MeshSegNet weights nor ToothGroupNetwork are usable
   as-is. This is a genuine gap across the entire open-source ecosystem as
   of this audit (per OpenSourceOrtho's own `segmentation-learned-backend.md`,
   last checked "June 2026").
2. **True per-tooth attachment/cut-placement geometry algorithm** — both
   projects treat attachments as authored metadata, not a computed geometric
   proposal.
3. **A dedicated, standalone IPR algorithm module** — same gap.
4. **Real (non-proxy) per-tooth STL export** — OpenSourceOrtho's own roadmap
   states their print-package still exports bounded proxy solids unless a
   real mesh is locally registered; true per-tooth vertex export is their own
   stated "next phase," not something already solved we can borrow.
5. **A validated, non-heuristic collision/proximity engine** — their
   `collisions-checked` is explicitly informational, not a gate; both
   projects still need real per-tooth mesh geometry (not proxy shapes) for
   accurate collision math.

## Licensing Risks (Summary)

| Risk                                                                        | Severity     | Mitigation                                                                                                                                                                                                                                |
| --------------------------------------------------------------------------- | ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Redistributing MeshSegNet's pretrained weights                              | High if done | Never commit weights; require user-supplied weights via env var/path, same as OpenSourceOrtho's own approach                                                                                                                              |
| Using ToothGroupNetwork code without permission                             | High if done | Treat as reference-only; do not import, adapt, or train from it                                                                                                                                                                           |
| Training any model on Teeth3DS+/3DTeethSeg'22                               | High if done | Do not use this dataset for any shipped/commercial model                                                                                                                                                                                  |
| Re-implementing OpenSourceOrtho concepts too literally (near-verbatim code) | Low–Medium   | Even though Apache-2.0 permits reuse, re-derive our own implementation from the documented concepts/interfaces rather than copy-pasting, to keep our own architecture coherent and avoid accidentally inheriting their dependency surface |
| OpenSourceOrtho's own license changing in a future release                  | Low          | Re-verify the LICENSE file at the exact commit/tag if/when we ever do more than reference it                                                                                                                                              |

## Recommended Integration Path (Future Phases — Not Now)

1. **Phase 3 (implemented):** `engines/segmentation.OnnxSegmentationEngine`
   composes validation, normalization, 15-feature preparation, an injectable
   ONNX adapter, output parsing, connected component extraction, deterministic
   ordering, and experimental provenance metadata. `adapters/meshsegnet` is
   prepared as a wrapper boundary only; no model or weights are included.
2. **Next segmentation step:** Verify a legally-cleared MeshSegNet-compatible
   ONNX artifact's exact tensor contract and benchmark it against a labelled,
   PHI-free/consented corpus. If weights are unavailable, the engine must
   remain explicitly unavailable rather than selecting a fixture.
3. **When staging/arch-analysis is prioritized:** Re-implement (not copy)
   the `ToothDelta`/`CoordinateFrame`/`rotation_renderable` pattern in
   `domain/treatment_plan`, respecting our own `DataProvenance` rules.
4. **When IPR/attachments are prioritized:** Design first-class domain
   models rather than following either project's metadata-bag approach.
5. **When export is prioritized:** Reference OpenSourceOrtho's manifest/hash
   pattern (engine version + plan hash + per-artifact SHA-256) as a design
   template for our own `docs`/`export` engine, implemented independently.
6. At each of these steps, add the relevant row(s) to
   [CLINICAL_BOUNDARIES.md](../CLINICAL_BOUNDARIES.md) and
   [REUSE_MATRIX.md](../REUSE_MATRIX.md) before writing code, per our
   existing repository rules.
