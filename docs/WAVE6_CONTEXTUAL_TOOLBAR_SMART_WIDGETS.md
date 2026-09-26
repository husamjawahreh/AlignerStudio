# Wave 6 — Contextual toolbar and smart widgets

The viewport reveals the next useful action from one resolver. It does not keep a permanent catalog of tools.

Live ToothInstanceNet inference did not run. This host remains **BLOCKED_BY_ENVIRONMENT**. Fixture geometry in browser evidence is test-only.

## Toolbar state machine

`resolveToolbar` in `apps/web/src/interaction/toolbar.ts` is the only viewport toolbar resolver. `buildContextualTools` remains the Wave 3 helper used by existing interaction tests. The live workspace does not call it.

Context order:

1. `processing` when stage status is PROCESSING
2. `blocked` when segmentation is `blocked_by_environment`
3. `failed` when stage status is FAILED or segmentation failed
4. `stale` when stage status is STALE, or the staging step is open and stored staging is stale, and nothing is selected
5. `unavailable` when segmentation is `not_available`
6. `one-tooth` or `multi-tooth` when the scene has a selection
7. otherwise the workspace: segmentation review, treatment setup, staging, refinement, validation, production, case, or idle

A selected tooth keeps `one-tooth` even when staging is stale. Regeneration is still added on staging or refinement.

## Action schema

Every item has `id`, `label`, `category`, `availability`, `reason`, `priority`, optional `shortcut`, `effect`, `reversible`, `destructive: false`, and `truthDependency`.

Placement:

- executable and priority 1–5: primary toolbar
- executable and priority 6–7: More
- not executable: withheld under Unavailable, with the availability value on the note

Camera presets move into More once a tooth is selected, so the primary row stays the selection and arch actions.

## Priority

1. workflow
2. selection
3. manipulation
4. viewport
5. review
6. utility
7. advanced

The header or the step form already owns the single next action. That id is suppressed so the toolbar does not repeat it. Cancel stays on the processing overlay.

## Availability

| Value | Meaning | Clickable |
| --- | --- | --- |
| `available` | The command exists and the current evidence allows it | yes |
| `unavailable` | The capability does not exist, or the dependency is missing | no |
| `blocked` | The environment prevents execution. This is not a model failure | no |
| `requires_review` | A result exists and still needs doctor review | yes, when it only changes view state |
| `stale` | A stored result is out of date and a real regenerate command exists | yes |

Unavailable and blocked items are not disabled buttons in the primary row.

## Widgets

`resolveWidgets` returns at most two widgets, ranked selection, current/target, validation, provenance, staging, processing, case dependency.

A widget is omitted when another surface already owns that fact:

- processing widget hides while the loading overlay is up
- provenance widget hides while the segmentation strip is visible
- staging widget hides while the stage timeline is visible
- validation widget hides on the validation step
- case-dependency widget hides while workflow orientation is visible

Current/target renders only when a stored target stage exists. Copy says stored geometry, not an approval. Staging copy does not say optimal. Validation copy does not show a score, a percentage, or a safe state. Fixture provenance says “Fixture / test-only” and “Not patient inference.”

## Commands

Toolbar ids and keyboard shortcuts call `handleTool` or `handleClearSelection`.

| Shortcut | Command |
| --- | --- |
| Esc | clear selection |
| F | fit selection |
| Home | fit case |
| 1 / 2 / 0 | upper / lower / both |
| Ctrl or Command Z | undo |
| Ctrl or Command Shift Z | redo |
| Delete | no clinical effect |

`undo` and `redo` are the only viewport command ids that touch the existing durable edit stack. Fit, arch, labels, isolate, and target visibility are view state. There is no second undo engine.

Move, rotate, lock, and apply stay on the existing tooth toolbar in refinement. The main toolbar does not add a second manipulation control.

## Viewport occupancy

The budget treats the viewport as dominant when its width exceeds both side panels and the height is at least 700. That holds at 1366×768, 1600×1000, and 1280×800. At most two widgets and 14 primary tools.

The toolbar sits on the viewport, not in a new chrome band. Widgets sit in the viewport header.

## Known limitations

- Live inference is still blocked. No NVIDIA driver, torch, or pointops is installed by this wave.
- Measure, segmentation correction, and the validation overlay are withheld. They are not implemented clinical tools.
- Manufacturing export stays on the production step. No manufacturing CAD was added.
- WP-14 and WP-15 were not started.
