# Wave 9 — Feature depth

**Date:** 2026-09-26  
**Verdict:** PASS WITH BLOCKER  
**This is not First Version acceptance.** Live ToothInstanceNet inference did not run. This host remains **BLOCKED_BY_ENVIRONMENT**.

The depth added here is the existing edit stack on Treatment Setup, plus an explicit capability matrix. No second planning, staging, validation, or production engine was added.

## Capability matrix

| Capability | State | Why |
| --- | --- | --- |
| Segmentation review | Blocked by environment | No live model on this computer. A test mesh is fixture-only |
| Tooth move, rotate, lock, exclude, reset, numeric edit, undo, redo | Executable when a plan is stored | Same edit stack in Treatment Setup and Refinement. No movement limits are configured, so a change is geometric |
| Current vs target | Executable when a target is stored | View toggle. Not approval |
| Save, restore, compare versions | Executable through the existing setup version controls | Durable plan versions, not a new store |
| Staging create and regenerate | Executable from an explicit action | Bound to the stored target. Labeled not clinically optimal |
| Stage inspection | Executable | Stage list, freshness, and truth state |
| IPR | Review only | A centroid distance is not a prescription. A doctor-entered amount stays an entered amount. No enamel threshold |
| Attachments | Review only | Candidates are not approved designs. Dimensions are not invented |
| Occlusion, roots, landmarks, clinical axes | Blocked by data on crown-only geometry | A generic mesh direction is not a clinical axis |
| Validation | Executable as review | Findings and unavailable checks. No score and no safety percent |
| Production export and QC | Executable as an engineering package | Shell, trimline, undercut, and manufacturing certification stay unavailable |
| Synthetic gingiva | Presentation only | Not clinical evidence |

## What changed in the workspace

Treatment Setup now shows the same selected-tooth controls and numeric inspector as Refinement when a plan is stored. Move and undo in the viewport toolbar point at that stack instead of a second command. The stored initial stage is the movement baseline. The engineering demo bundle is not used as the baseline for another case.

Staging still says the proposal is not clinically optimized. IPR and attachment review stay on the existing proposal panels.

## Real case versus fixture

Official real-case timings and production evidence remain the WP-10 and WP-12 records. They are not restated here as a new clinical segmentation. Fixture browser screenshots are generated test meshes. `classifyFeatureDepth` marks test-only segmentation as `fixture_only`.

## Remaining gaps before a First Version

- Live ToothInstanceNet inference.
- Contact-based IPR, not centroid review values.
- Attachment geometry and manufacturing binding.
- Occlusion that depends on a real registration, and roots or landmarks that depend on evidence that is not in a crown scan.
- Clinical movement limits, only if a real limit set is configured.
- Manufacturing shell, trimline, undercut, and certification.
- Validation that can say more than the current geometric findings, without becoming a score.

## Tests

Wave 9 unit tests cover the matrix and Treatment Setup undo ownership. Frontend Vitest: 204 passed. Typecheck, ESLint on the touched files, and the production web build passed.

Browser QA passed at 1366×768, 1600×1000, and 1280×800 in 4.8 minutes. Evidence is `.research/tmp/wave9_browser_qa/`. Those screenshots use generated test meshes.

The three previously unconfirmed WP-10 tests passed in one run (307 seconds): real-case production evidence, the WP-09 validation regression, and the manufacturing-boundary check. A later combined WP-04 through WP-09 plus WP-12 and WP-13 run printed 17 passes and was stopped before its summary, so that combined run is not a completed regression record. WP-12 and WP-13 had already passed together earlier in Wave 8 (15 tests).

WP-14 and WP-15 were not started. Wave 10 of this gate was not started.
