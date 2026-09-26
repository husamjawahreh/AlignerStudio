# Wave 10 — Adaptive inspector / no-scroll

**Date:** 2026-09-26  
**Verdict:** PASS WITH BLOCKER  
**This is not First Version acceptance.** Live ToothInstanceNet inference did not run. This host remains **BLOCKED_BY_ENVIRONMENT**.

The inspector is one resolver, `buildInspectorModel`. It explains the current selection or job. It does not start segmentation, planning, staging, or validation, and it does not rebuild the scene.

## Information hierarchy

Level 1 is identity and state: tooth or group, `tooth_ref`, FDI only when that FDI is authoritative, arch, workspace, and segmentation truth.

Level 2 is the stored CAD fact that the step can use: current transform, target only when a target is stored, lock and exclude, stage, validation freshness, and review state. Empty clinical fields are omitted. They are not shown as zero.

Level 3 is the control that does not already live on another surface. Numeric edit, lock, exclude, apply, reset, and undo stay on the tooth inspector. Move and rotate stay on the tooth toolbar.

Level 4 is Advanced Details: hashes, provenance, backend, source, and timestamps. It stays collapsed.

## Inspector states

| Context | Mode | What it shows |
| --- | --- | --- |
| No case | `none` | Next step is create a case. No tooth fields |
| No selection | workspace mode | Step, readiness or plan/stage/validation/production facts, one next label |
| One tooth | `tooth` | Identity, stored current transform, target only if stored |
| Several teeth | `group` | Count, arches, identity agreement, whether all are editable. No single transform |
| Processing | `processing` | Phase, elapsed, server progress only when the server sent it. No invented percent or ETA |
| Blocked | `blocked` | Environment blocker. Retry is not offered |
| Failed | `failed` | Server or segmentation failure text and recovery. Advanced details keep provenance |
| Cancelled | `cancelled` | Cancelled, and not a failure |
| Interrupted | `interrupted` | Interrupted, and not a cancellation. A new job does not resume mid-stage |
| Requires review | `requires_review` | Analysis or intake when identity is unresolved or fixture-only |
| Unavailable | `unavailable` | Missing dependency. Not a count of zero teeth |
| Treatment Setup | `treatment-setup` | Version and stale state when nothing is selected |
| Staging | `staging` | Stage count, selected stage, freshness, and the not-clinically-optimal limit |
| Refinement | `refinement` | Edit count. IPR and attachments stay in a review fold |
| Validation | `validation` | Findings, technical severity, unavailable checks, freshness. No score |
| Production | `production` | Source and production state. Manufacturing certification is not claimed |

A running, failed, cancelled, or interrupted job replaces the tooth inspector. A selected tooth replaces the workspace summary. An environment blocker replaces the workspace summary when nothing is selected. A selected tooth during that blocker still inspects the tooth.

## Action ownership

| Action | Owner | Condition | Duplicate removed |
| --- | --- | --- | --- |
| Workflow navigation | Workflow header | Always | Inspector step buttons |
| Create case | Left step form | No case | Inspector Create Case button |
| Review segmentation | Left step form | Analysis | Right analysis inspector |
| Retry segmentation | Contextual toolbar | Failed, cancelled, or interrupted | Inspector Retry button. Blocked environment still withholds retry |
| Create treatment plan | Left step form | Treatment Setup | Inspector does not generate a plan |
| Save, restore, compare | Left step form | Stored plan | Right setup version buttons |
| Regenerate staging | Left staging form | Staging | Toolbar regenerate on that step |
| Fit, isolate, camera | Contextual toolbar | Scene available | Inspector Fit and Isolate labels |
| Move, rotate | Tooth toolbar | One tooth in Treatment Setup or Refinement | Left refinement Move and Rotate |
| Numeric edit, lock, exclude, apply, reset, undo, redo | Inspector | One editable tooth | Tooth toolbar lock, exclude, apply, and cancel; toolbar undo and redo |
| Reset all edits | Inspector | Refinement | No second reset-all |
| IPR and attachment review | Inspector fold | Refinement | Proposal editors on Treatment Setup |
| Cancel and remaining time | Processing overlay | Job running | Inspector ETA and a second remaining-time line |
| Export | Left production form | Production | Right export panel |

The source list is `ACTION_OWNERSHIP` in `apps/web/src/interaction/actionOwnership.ts`. Commands still go through the existing handlers.

## Responsive strategy

The page shell does not scroll. The inspector column does not scroll. Density comes from shorter rows, collapsed Advanced Details, and a collapsed IPR fold. Truth and recovery stay visible. The left step form can scroll inside its rail because that form is the step's working surface. The viewport column stays wider than the inspector.

## Interaction consistency

Selection, move, rotate, numeric edit, lock, exclude, reset, undo, redo, regenerate, fit, and workflow navigation use the existing command path. There is no second edit stack and no React Three Fiber scene.

## Performance

`buildInspectorModel` is pure. The scene graph memo depends on the review stage, scan buffers, and layer registry. Inspector context is not one of those dependencies, so a context change does not rebuild geometry or the BVH and does not issue an API request.

The Wave 10 unit test calls the resolver 2000 times and requires a mean under 1 ms per call. That is negligible next to segmentation, staging, or validation.

## Browser QA

Evidence is `.research/tmp/wave10_browser_qa/`. The Playwright spec is `tests/e2e/wave10.inspector.spec.ts`. It passed at all three viewports (57 screenshots, 54 measurements). It covers launch, intake, analysis, no selection, one tooth, multiple teeth, treatment setup, staging, refinement, validation, production, processing, blocked, failed, cancelled, interrupted, requires review, unavailable, workspace transitions, selection persistence, undo, and stale regenerate.

No-scroll measurements, page scroll height / client height, inspector content / inspector box, viewport column width vs inspector width:

| Viewport | Page | Inspector | Viewport column | Inspector width |
| --- | --- | --- | --- | --- |
| 1366×768 | 768 / 768 | 706 / 706 | 878 | 248 |
| 1600×1000 | 1000 / 1000 | 934 / 934 | 1048 | 280 |
| 1280×800 | 800 / 800 | 738 / 738 | 792 | 248 |

Every measured state had no page scroll and no inspector overflow. The viewport column was wider than the inspector in all 54 measurements.

Fixture crowns in those screenshots are generated test meshes. They are not clinical segmentation.

## Truth and safety

GeometricValidationEngine is unchanged. FDI is shown only when it is authoritative. Missing teeth, roots, landmarks, clinical axes, occlusion, IPR prescriptions, attachment prescriptions, manufacturing certification, and clinical approval are not invented. Staging still says it is not clinically optimized. Validation has no score and no safety percent. A missing check is not a pass.

## Remaining limitations

- Live ToothInstanceNet inference is blocked on this computer.
- The left step form still scrolls inside its own rail when the form is taller than the workspace.
- IPR remains a review candidate from centroid distance, not a prescription.
- Production export is an engineering package, not manufacturing readiness.

## Gate note

This document was added because the gate previously said Wave 10 had not been started. That sentence is updated in the gate result log. WP-14 and WP-15 were not started. Wave 11 was not started. This result is not First Version acceptance.
