# Wave 3 — Clinical Segmentation Review

**Date:** 2026-09-26  
**Verdict:** PASS WITH BLOCKER  
**Blocker:** Live ToothInstanceNet inference is still `BLOCKED_BY_ENVIRONMENT` on this host. The review workspace reports that state. It does not substitute fixture teeth or invent FDI numbers.

## What the review screen shows

Without scrolling the left rail, the analysis viewport shows:

- the case reference
- upper and lower instance labels, or “Not available”
- segmentation state
- persisted instance count only when instances exist
- unresolved identity count
- confidence only for real-model inference that reported a number
- provenance: real-model inference, fixture/test-only, blocked, failed, or not available
- the next action

Blocked, failed, and not-available results do not display a clinical zero. The dental map says the segmentation is unavailable instead of drawing empty tooth slots.

## Identity

- Selection is the semantic `tooth_ref` (`toothRef`, otherwise `instance:{id}`). It is not a mesh index.
- The map, the 3D label, and the inspector use that same key.
- FDI text is rendered only when `planningMode` is `clinical_fdi`, `identificationStatus` is identified, resolved, or verified, and the tooth is not fixture or experimental.
- A stored FDI on a fixture record stays in advanced/test metadata. The doctor-facing label stays `tooth_ref` and unresolved.
- Absence of a tooth in a crown-only result is “Identity/data not established”. It is not a missing-tooth diagnosis.

## What this wave did not do

- No live ToothInstanceNet run.
- No CUDA, PyTorch, or pointops install.
- No replacement segmentation model.
- No manufacturing CAD.
- No WP-14 desktop packaging.
- No WP-15 final real-case gate.
- No change to GeometricValidationEngine authority.
- No synthetic gingiva in clinical calculations. Gingiva meshes stay `presentationOnly: true`.

## Browser evidence

Headless Chromium captures, when produced, live under `.research/tmp/wave3_browser_qa/`. Those images are UI evidence. They are not clinical segmentation evidence. Fixture geometry, if shown, is labeled fixture/test-only. A blocked runtime is labeled blocked.
