# Pre-First-Version Interaction Model

**Status:** Implemented in Wave 3.  
**Date:** 2026-09-26  
**Gate:** `PRE_FIRST_VERSION_WORLD_CLASS_GATE.md`  
**Code:** `apps/web/src/interaction/model.ts`, `apps/web/src/components/workspace/ClinicalChrome.tsx`, `apps/web/src/app/App.tsx`

This is the doctor-facing interaction contract. It does not replace GeometricValidationEngine, the treatment undo stack, or ToothInstanceNet.

## Questions the workspace answers

- Where am I? One workflow bar: Case Intake, Analysis (Segmentation Review), Treatment Setup, Staging, Refinement, Validation, Production.
- What am I looking at? The 3D viewport, plus one segmentation-review strip when a segmentation state exists.
- What can I do? One contextual toolbar. Unavailable clinical tools are listed under Unavailable, not shown as working buttons.
- What should I do next? The current step has one primary button. The header shows the next action only when that action lives on a different step.
- What changed? Clinical undo/redo uses the existing durable edit stack. Selection and camera changes are not clinical undo.
- What is verified? FDI is shown only when the persisted tooth is `clinical_fdi`, identity is identified/resolved/verified, and the record is not fixture or experimental.
- What requires review? Unresolved teeth keep `tooth_ref`. Fixture output is labeled fixture/test-only.

## Layout

- Compact top bar: case, workflow, one primary status, optional next action.
- Left rail: the step form (intake, analysis findings, setup, staging, refinement, validation, production).
- Center: viewport. It is the largest region at 1366×768 and 1600×1000.
- Right inspector: adaptive. Hidden to a narrow rail when minimized. Case readiness has one home (`data-readiness-surface="primary"`).
- Dental map: viewport widget. One entry per persisted tooth instance. A blocked segmentation is “unavailable”, not “zero teeth”.
- No second status bar. The only `data-status-surface="primary"` node is the header status.

## Mouse

- Left click on a tooth selects that `tooth_ref`.
- Shift, Ctrl, or Command click toggles multi-select.
- Click on empty viewport clears selection.
- Hover previews the tooth and the matching map item.
- A pointer move longer than a click does not select. That keeps orbit separate from selection.
- Gizmo dragging does not change selection.

## Keyboard

Ignored while focus is in a text field.

| Input | Action | Clinical undo |
| --- | --- | --- |
| Esc | Clear selection | No |
| F | Fit selection | No |
| Home | Fit case | No |
| 1 / 2 / 0 | Upper / lower / both | No |
| Delete / Backspace | No effect. Clinical teeth are not deleted. | No |
| Ctrl/Cmd+Z | Undo the last durable edit | Yes |
| Ctrl/Cmd+Shift+Z | Redo | Yes |

Shortcut text is on the toolbar button title, not a permanent legend.

## Camera

Commands: fit case, fit arch, fit selection (one tooth or the selected `tooth_ref` set), occlusal, front, right lateral, reset. Transitions use the existing StageViewer tween. Ordinary selection does not move the camera.

## Toolbar and inspector

Toolbar contents follow context: view tools with no selection; fit and isolate for one tooth; fit for a group; target and movement only when a treatment result exists. Measure, IPR, and segmentation correction are named under Unavailable with the reason. They are not disabled buttons that look ready.

The inspector shows case, blocked segmentation, one tooth, or a group. Advanced details hold backend, provenance, and source hash. Confidence is shown only when real-model inference reported a number.

## Truth states

`processing`, `completed`, `failed`, `blocked_by_environment`, `cancelled`, `interrupted`, `stale`, `requires_review`, `not_available`.

Each state says what happened, what to do next, what is unavailable, and whether a new job is a safe retry. Processing shows elapsed time and phase when the server sent them. Remaining time is “No reliable remaining-time estimate” unless this computer has completed the same kind of job often enough to support an estimate. An estimate is labeled estimated and is not a guarantee. See `docs/WAVE8_PERFORMANCE_REMAINING_TIME.md`.

## Undo

WP-04 / WP-05 / WP-13 durable edits stay on the existing stack. A grouped gizmo drag remains one undo unit. A numeric edit remains one undo unit. Refresh still shows the stored edit history. This wave did not add a second undo engine.

## Known limits

- Live ToothInstanceNet inference is not run here. A blocked host must look blocked.
- Boundary edit, split, merge, and identity correction are not implemented. The toolbar says they are unavailable.
- Measure and IPR are not active tools.
- Synthetic gingiva is presentation-only and is not written into the review payload.
- WP-14 and WP-15 were not started.
