# Wave 7 — Workflow simplification

One clinical journey. One current step. One next action.

Live ToothInstanceNet inference did not run. This host remains **BLOCKED_BY_ENVIRONMENT**. Fixture geometry in browser evidence is test-only.

## Workflow state machine

`resolveWorkflow` in `apps/web/src/workflow.ts` is the only workflow-state resolver. `buildWorkflowSteps` calls it. The workspace does not keep a second engine.

Launch is the application shell. It always opens Case Intake. It is not an eighth step.

Each step exposes:

| Field | Meaning |
| --- | --- |
| `id` | Stable step id |
| `label` | Doctor-facing name |
| `state` | `not_started`, `available`, `active`, `completed`, `blocked`, `unavailable`, `stale`, `failed`, or `requires_review` |
| `dependency` | What the step needs |
| `completionCondition` | When the step is satisfied. Satisfaction is not a clinical approval |
| `nextAction` | The same canonical action on every step |
| `reason` | Why the step is blocked, unavailable, failed, or stale |
| `navigationAllowed` | Whether the step can be opened |
| `emptyState` | What is missing, why it matters, and what can be done now |

The current step is `active` only while work is still open. A blocked, failed, stale, or review state stays visible when that step is current.

`resolveNextAction` remains the action catalog. `resolveWorkflow` calls it, so the header, the step brief, and toolbar suppression share one action id.

## Dependencies

| Step | Needs | Completion | If the need is missing |
| --- | --- | --- | --- |
| Case Intake | Nothing. Launch always opens it | A case and both scans | The step stays available |
| Analysis | Both scans | Segmentation evidence from the installed model | Blocked until scans exist. An environment block, a failure, or a test-only result does not complete the step |
| Treatment Setup | Segmentation evidence for tooth-level planning | A stored plan and target | The step opens and says the target is missing. It does not create a plan |
| Staging | A stored target | Stages stored for the current target and not out of date | Opens to explain the gap. Does not build stages |
| Refinement | A stored plan | Optional. A durable edit marks it used | Opens to explain the gap. Does not move teeth |
| Validation | A stored plan | A validation run for the current version | A missing or unavailable check is not a pass |
| Production | A stored plan | Not claimed while manufacturing capabilities are unavailable | Limits stay visible |

Optional capabilities that are not implemented do not pretend to be broken buttons. Boundary edit, split, merge, identity correction, and measure stay listed as unavailable text.

## Entry and exit

Opening a step calls `resolveWorkflowNavigation` and then changes the current step. That decision is only `navigate` or `inspect`.

| Intent | What happens |
| --- | --- |
| `stay` | The current step is clicked again |
| `review` | An earlier step is opened |
| `enter` | A later step whose prerequisites allow it is opened. A blocked step that can explain itself is opened without starting work |
| `explain` | A step that cannot be opened leaves the current step in place and shows the dependency |

Long work starts only from an explicit operation:

| Operation | Examples |
| --- | --- |
| `navigate` | Open staging, open a stored plan, import focus |
| `inspect` | Review a blocker, review findings, review production limits |
| `compute` | Review segmentation, retry segmentation, create a treatment plan |
| `regenerate` | Regenerate staging, refresh validation |
| `apply` | Create a case, export, cancel processing |

`open-treatment-plan` navigates. It does not start processing. `create-treatment-plan` is the explicit compute.

## Next-action consistency

Every step record carries the same `nextAction` id. The header button is shown only when the current step form does not already own that action. The step brief’s next line is that same label. The toolbar suppresses that id. Surfaces may shorten the wording, and they do not offer a different action as the next step.

## Navigation and recovery

Browser back and forward read `history.state.workflowStep` and restore that step. They do not start segmentation, planning, staging, or validation.

Refresh still uses the WP-13 case and step memory in `caseWorkspacePersistence.ts`. A stored processing status is loaded again. Durable edits stay on the existing undo stack and the treatment record. A stale flag comes back from the stored treatment, not from a new run.

Recovery stays on the step that failed:

| Situation | Recovery |
| --- | --- |
| Analysis blocked by the computer | Review the blocker. Retry stays unavailable |
| Analysis failed | Retry starts a new run only when chosen |
| Treatment target missing | Show the dependency. Create a plan only with the explicit action |
| Staging out of date | Regenerate staging when chosen |
| Validation out of date | Refresh validation when chosen |
| Production incomplete | Review the manufacturing limits |

The recovery path does not send the doctor back to Launch.

## Empty states

Each empty state names the missing piece, why it matters, and the valid action. Examples: “No treatment target yet”, “Segmentation cannot be completed on this computer”, “No validation run for this treatment version”. A blocked segmentation is not shown as zero teeth.

## Processing boundaries

Step navigation does not post a segmentation run or a treatment run. Those posts happen from Review segmentation, Retry segmentation, and Create Treatment Plan. Staging and validation refresh stay on their own buttons. Before those actions, the step shows the current evidence. After a run starts, processing status is the status line and the processing overlay. Refresh keeps an in-progress run in progress when the server still reports it.

## Known limitations

- Live inference is still blocked. No NVIDIA driver, torch, or pointops is installed by this wave.
- Test-only segmentation does not complete Analysis.
- Production does not claim manufacturing readiness. Manufacturing CAD was not added.
- Boundary edit, split, merge, identity correction, and measure are not implemented.
- Header action `headerNextAction` in the interaction model remains a legacy helper. The workspace does not call it.
- Browser evidence for the full navigation matrix is recorded at 1366×768. The same matrix at 1600×1000 and 1280×800 was not reconfirmed after the refresh-persistence fix.
- WP-14 and WP-15 were not started. Wave 8 and later were not started.
