# Wave 5 — Smart UI/UX

**Date:** 2026-09-26  
**Verdict:** PASS WITH BLOCKER  
**Live ToothInstanceNet inference:** no. This host remains **BLOCKED_BY_ENVIRONMENT**.

This wave changes how the workspace answers a doctor’s questions. It does not add clinical algorithms, manufacturing CAD, or a second 3D engine. GeometricValidationEngine stays authoritative. Synthetic gingiva stays presentation-only. ToothInstanceNet stays the baseline segmentation model.

## Information architecture

Each fact has one home:

1. **Workflow navigation** — the header step list. It shows where you are, which earlier steps are complete, and which later steps are blocked. An environment-blocked analysis step is marked separately from a step that is waiting on a previous result.
2. **Viewport** — the 3D scene, the dental map, and the selection widget.
3. **Contextual action** — exactly one next action. If the current step already contains that control, the header does not repeat it. Cancel lives on the processing overlay, not in the header.
4. **Adaptive inspector** — the right rail. It changes with selection and with the operation state.
5. **Optional widget** — the selection widget only, and only when something is selected. Arch, processing, truth, and next action are not given extra cards, because those already have a home.
6. **Advanced details** — hashes, backend, model provenance, and file triangle counts. They stay collapsed.

The left column is the step’s own work. It is not a second dashboard. The segmentation strip keeps counts and provenance. It does not repeat the next-action sentence.

Case readiness has one node: `data-readiness-surface="primary"` on the case inspector. Processing status is not copied there.

## Next-action resolver

`resolveNextAction` in `apps/web/src/interaction/nextAction.ts` reads persisted UI state and returns one executable action, or null while a local task is busy and cannot be cancelled.

| Evidence | Action | What it does |
| --- | --- | --- |
| No case | Create Case | Creates the case record |
| Case, missing arch | Import upper scan / Import lower scan / Import upper and lower scans | Focuses the missing STL input |
| Segmentation blocked by environment | Review segmentation blocker | Opens analysis. Does not start a retry |
| Segmentation not run | Review segmentation | Runs segmentation review |
| Failed, cancelled, stale, interrupted, or not available | Retry segmentation | Starts a new job. No mid-stage resume |
| On Treatment Setup with no stored target and no tooth instances | Review treatment setup dependency | Opens the explanation. Does not create a plan |
| Instances present, identity unresolved | Review unresolved identities | Opens review. No correction tool is offered |
| Instances present, identity resolved, no plan | Create Treatment Plan | Creates a plan. Does not approve it |
| Plan exists, staging stale | Generate / Regenerate Staging | Uses the existing staging action |
| Plan exists, validation stale | Dynamic staging refresh | Uses the existing recompute action |
| Plan exists, production capabilities missing | Review production limits | Opens production. Does not create appliances |
| Otherwise | Open Staging, Review Findings, or Export Package | Only when that step can be opened |

Labels are the labels of controls that already exist. IPR, attachments, identity correction, and clinical approval are not suggested.

## Truth-state UI

The header status uses one of: processing, completed, failed, blocked by environment, cancelled, interrupted, stale, requires review, not available.

An environment blocker is labeled “Environment blocker, not a model failure.” It is not a green state and not a spinner that runs forever. Fixture and test-only output is dashed and named. Verified and computed use the normal text color. They do not mean clinically approved. `truthImpliesClinicalApproval` is always false.

## Inspector

| Context | What it shows |
| --- | --- |
| No case | Create Case |
| Case, segmentation not run | Patient, case, segmentation state |
| One tooth | tooth_ref, FDI only if authoritative, arch, identity, segmentation, target if stored |
| Several teeth | Count, arches, whether identity agrees. Fit selection only. Mixed identity gets no shared clinical action |
| Processing | Phase, indeterminate progress unless the server sent a percent |
| Blocked | Blocker, retry not offered, source scans not reported as changed |
| Failed, cancelled, interrupted, stale | What the durable state was, whether retry is a new job, which other steps remain |
| Requires review / fixture | Unresolved identity or explicit fixture/test-only |
| Unavailable | Why, the dependency, and what would make it available |

Hashes and backend fields stay under Advanced details. Warnings and blockers stay outside that disclosure.

## Toolbar

Visible, in order: selection fit and isolate, then case/arch fit and arch filter, then camera presets, then labels and stored target/movement when those exist.

Gingiva, wireframe, tooth visibility, and reset sit under More. Measure, IPR, and segmentation correction stay under Unavailable with a reason. They are not disabled buttons.

## Notifications

Local failures render once, in the step column, and only when the sentence is not already the primary status. Export text uses one transient notice, and only when it differs from the status line and the inline error. The processing overlay is the processing surface. It does not add a second status marker.

## Processing and failure

Processing shows the server phase and elapsed time when the server sent them. A percent is shown only when `overall_progress` is a real number. Otherwise progress is indeterminate. Remaining time is “No reliable remaining-time estimate.” A historical sample can be labeled as a sample and is never stored as a remaining-time estimate. This workspace does not invent one.

Cancel is available when a processing job id exists. It calls the existing cancel endpoint. Source scans are not deleted.

Failure copy answers what happened, whether the record says the scans changed (it usually does not), whether retry is a new job, what to do now, and which other steps remain. The server’s message is kept. It is not replaced with “Something went wrong.”

## Case intake

Upper and lower crown STL are the import. The panel says roots, bite registration, and occlusion are not established from those files. There is no registration control. File size and validity stay on the row. Triangle count sits under File details. The content hash stays with the stored upload and is not repeated in the form.

## Tooth review and dental map

A selected tooth keeps its neighbors in view. The label is tooth_ref unless FDI is authoritative. Unresolved identity says so and does not offer a correction tool. Fixture teeth are marked fixture/test-only.

The dental map lists persisted instances only, split by arch. It does not draw empty FDI positions. Empty space is not a missing-tooth diagnosis. Hover and selection stay synchronized with the viewport.

## Keyboard and responsive layout

Escape clears selection. F fits the selection. Home fits the case. 1, 2, and 0 filter arches. Ctrl/Cmd+Z and Ctrl/Cmd+Shift+Z remain the clinical undo stack. Delete does not remove tooth data. Focus is visible on buttons, inputs, and summaries. Shortcuts are ignored while typing in a field. 3D orbit is unchanged.

Layout budgets at 1366×768, 1600×1000, and 1280×800 keep the viewport larger than the rail and the inspector, with no page scroll. The inspector can collapse. Workflow steps scroll inside the header instead of clipping the page.

## Performance

Next-action resolution, inspector assembly, and toolbar splitting are pure functions over small state. They do not serialize tooth geometry. Two thousand resolver calls stay under 50 ms in the unit test. Selection, hover, and label changes still do not rebuild `BufferGeometry` or the BVH.

## Known limitations

- Live ToothInstanceNet inference did not run. The runtime blocker is unchanged: no NVIDIA driver, torch, or pointops on this host.
- No measured per-case remaining time is available, so the UI does not show one.
- Boundary edit, split, merge, identity correction, measure, and IPR are still unavailable.
- Browser screenshots that use fixture crowns are test meshes, not clinical segmentation validation.
- WP-14 and WP-15 were not started. Wave 6 and later were not started.
