# World-Class Interaction Model

**Status:** Wave 3 implemented the interaction model described here. See `docs/PRE_FIRST_VERSION_INTERACTION_MODEL.md`. Live ToothInstanceNet inference remains blocked.  
**Date:** 2026-09-26  
**Gate:** `PRE_FIRST_VERSION_WORLD_CLASS_GATE.md` Wave 3.  
**Current product:** clinical-CAD workspace with a truthful segmentation-review state. Not a completed real-model segmentation.

This document defines the future interaction system. It is one model, not a list of visual polish items. A doctor must be able to answer these questions without opening a technical panel:

- Where am I?
- What am I looking at?
- What can I do?
- What should I do next?
- What changed?
- What is verified?
- What requires review?

Acceptance is not “the panels are smaller.” The tests in section 10 of the Wave 2 command are the bar.

Legend used below:

- **IMPLEMENTED** — behavior exists in the current shell.
- **VERIFIED** — checked against current code in this command. Not a clinical acceptance.
- **PLANNED** — required by this model and not built yet.
- **REQUIRES_REVIEW** — exists, but the doctor-facing meaning is ambiguous.

## Current architecture (VERIFIED)

The shell is a seven-step workflow in `apps/web/src/workflow.ts`: Case Intake, Analysis, Treatment Setup, Staging, Refinement, Validation, Production. `App.tsx` owns the step, the processing job, and the undo stack. `useToothSelection` owns selection by `tooth_ref`, with an additive multi-select foundation. `StageViewer` uses OrbitControls, BVH picking on tooth meshes, and presentation-only gingiva. Commands can match `mod+z` in `design-system/commands.ts`, and refinement exposes an Undo control.

What fails the doctor questions today (VERIFIED, not redesigned):

- Status, readiness, and processing are repeated in the left panel, right inspector, header, and overlay.
- Analyze Case and Review Treatment Setup start different heavy jobs under overlapping names.
- The viewport is the center column, but fixed side rails and engineering sections compete with it.
- Selection reveals some tooth tools, and the same actions also live in step panels.

## Principles (PLANNED)

Direct manipulation: change the tooth in the viewport when the operation is spatial. Contextual tools: show a tool only in the step and selection where it applies. Progressive disclosure: the first screen answers the seven questions; measurements, hashes, and model names sit under Advanced. Spatial consistency: pick, fit, isolate, and undo mean the same thing in every step. Selection first: an empty selection shows view tools; a tooth selection shows tooth tools. Viewport dominance: rails yield to the model. One location: each action has one primary control. Clear feedback: started, working, completed, failed, requires review. Undoable: doctor edits that the session can reverse stay on one undo stack.

Identity rule, unchanged: if FDI is not established, the label is `tooth_ref` and the state is review-required. Do not invent a number.

## Interactions

### 1. Navigation

**What.** Move among Case, Analysis, Treatment Plan, Staging, Refinement, Validation, Production.  
**When.** After the previous step has a truthful result, or when the doctor is only inspecting an earlier result.  
**Where.** One step indicator on the viewport frame. **PLANNED.** Today the header nav and contextual buttons both move steps (**IMPLEMENTED**, **REQUIRES_REVIEW**).  
**Why.** The doctor must see where they are.  
**Feedback.** The current step name, and blocked steps that say why they are blocked.  
**Next.** The single primary action for that step.

### 2. Viewport composition

**What.** The scan or tooth meshes occupy the visual center. Side rails are contextual and collapsible.  
**When.** Always after a case exists.  
**Where.** Center stage (`StageViewer`). **IMPLEMENTED** as a center column between fixed rails. Full dominance is **PLANNED**.  
**Why.** The model is the workspace.  
**Feedback.** Empty state explains that scans are missing. A loaded state names the arch and the view.  
**Next.** Fit the case, or select a tooth.

### 3. Selection

**What.** Choose one tooth by `tooth_ref`.  
**When.** A segmented tooth mesh is on screen.  
**Where.** Click the tooth in the viewport. **IMPLEMENTED** in `useToothSelection` and StageViewer picking. Gingiva is not pickable (**VERIFIED**).  
**Why.** Selection is the primary primitive.  
**Feedback.** The tooth highlights. The inspector names `tooth_ref` or FDI only when FDI exists.  
**Next.** The contextual tooth tools.

### 4. Hover

**What.** Preview which tooth is under the pointer without selecting it.  
**When.** The pointer is over a tooth and no drag is active.  
**Where.** Viewport. **PLANNED.** Current picking selects; hover preview is not a separate contract.  
**Why.** The doctor should see the target before committing.  
**Feedback.** A light highlight and the same identity label used for selection.  
**Next.** Click to select, or move away to clear the preview.

### 5. Multi-selection

**What.** Add or remove teeth from a set.  
**When.** A command that needs more than one tooth is active.  
**Where.** Modifier-click in the viewport. Additive keys exist in `useToothSelection` (**IMPLEMENTED** foundation). A doctor-facing multi-select mode is **PLANNED**.  
**Why.** Some reviews compare neighbors. Most actions stay single-tooth so the default stays simple.  
**Feedback.** Each member is marked. The inspector says how many are selected.  
**Next.** Apply the group command, or clear the set.

### 6. Direct manipulation

**What.** Move or rotate the selected tooth on the model.  
**When.** Treatment Setup or Refinement, and the tooth is selected.  
**Where.** A gizmo on the tooth. **IMPLEMENTED** in the viewer for the refinement path. Making it the only primary control is **PLANNED**.  
**Why.** Spatial edits should happen on the object.  
**Feedback.** The tooth moves, the delta is numeric only in Advanced, and the edit is marked unsaved until undo state records it.  
**Next.** Undo, or continue to the next tooth.

### 7. Tool discovery

**What.** Find the action that matches the current step and selection.  
**When.** The doctor looks for what they can do.  
**Where.** One contextual toolbar on the viewport. **PLANNED.** Today actions repeat in `workflow.ts`, step panels, and the viewer chrome (**REQUIRES_REVIEW**).  
**Why.** Tools should not be hunted through forms.  
**Feedback.** Disabled tools say why, in one line.  
**Next.** Run the enabled primary action.

### 8. Contextual toolbar

**What.** No selection: View, Upper, Lower, Occlusion, Fit. Tooth selected: Move, Rotate, Isolate, Fit selected.  
**When.** The selection or step changes.  
**Where.** Viewport edge. **PLANNED.**  
**Why.** Irrelevant tools stay hidden.  
**Feedback.** The toolbar title matches the selection.  
**Next.** Invoke one tool. There is no second copy in the side panel.

### 9. Smart widgets

**What.** A small case, tooth, or validation summary that appears only when that object is current.  
**When.** A case is open, a tooth is selected, or validation has findings.  
**Where.** Near the viewport, not a permanent dashboard. **PLANNED.**  
**Why.** Widgets must not become another status wall.  
**Feedback.** Each widget has one truth state: verified, computed, requires review, not available, failed, or blocked.  
**Next.** Open the related step, or dismiss the widget by changing selection.

### 10. Adaptive inspector

**What.** The right side shows the selected object only: case, tooth, setup, or validation finding.  
**When.** The selection or step changes.  
**Where.** One inspector. **PLANNED.** Today intake, analysis, and setup each repeat readiness (**REQUIRES_REVIEW**).  
**Why.** One fact has one home.  
**Feedback.** Sections that do not apply are absent, not disabled duplicates.  
**Next.** Edit the selected object, or open Advanced for hashes and model identity.

### 11. Keyboard shortcuts

**What.** A short set: undo, redo, fit, isolate, clear selection, next and previous step.  
**When.** Focus is on the workspace and the user is not typing in a field.  
**Where.** `design-system/commands.ts` can match shortcuts (**IMPLEMENTED** foundation). A published clinical map is **PLANNED**.  
**Why.** Experts should not depend on the pointer for repeated actions.  
**Feedback.** The same result as the toolbar button, including the same undo entry.  
**Next.** Continue, or undo.

### 12. Mouse interactions

**What.** Click selects. Drag on empty space orbits. Drag on a gizmo edits. Right-drag or modifier-drag pans. Wheel dollies.  
**When.** The pointer is over the viewport.  
**Where.** StageViewer OrbitControls (**IMPLEMENTED** for orbit). The full click-versus-drag contract is **PLANNED** so orbit does not steal a selection click.  
**Why.** Camera motion and tooth edits must not be the same gesture.  
**Feedback.** The cursor shows orbit, pan, or edit.  
**Next.** Release to commit the camera or the edit.

### 13. Camera controls

**What.** Orbit, pan, and dolly around the active arch or tooth.  
**When.** The doctor is inspecting, not editing a gizmo.  
**Where.** Viewport. **IMPLEMENTED** via OrbitControls.  
**Why.** The doctor chooses the view without a form.  
**Feedback.** The view name stays visible when a preset is active.  
**Next.** Select a tooth, or restore a preset.

### 14. View presets

**What.** Front, right, left, occlusal, upper, lower.  
**When.** The doctor asks for a standard dental view.  
**Where.** The view group in the contextual toolbar. StageViewer already has preset directions (**IMPLEMENTED**). One toolbar home is **PLANNED**.  
**Why.** Presets are faster than hunting a camera.  
**Feedback.** The preset name is shown. Upper hides the lower mesh and the reverse.  
**Next.** Fit, or select.

### 15. Focus and fit

**What.** Fit the whole case, or fit the selected tooth.  
**When.** After load, after a step change, or when the doctor asks.  
**Where.** Viewport commands. **PLANNED** as two explicit actions. The viewer can frame geometry today (**IMPLEMENTED** capability).  
**Why.** The object of interest must land in frame.  
**Feedback.** The camera moves. The button state shows case versus selection.  
**Next.** Inspect or edit what is framed.

### 16. Current versus target

**What.** Show the current tooth and the planned target without mixing them.  
**When.** Treatment Setup, Staging, or Refinement, and a plan exists.  
**Where.** Viewport layers. Pair rendering exists when a tooth is selected (**IMPLEMENTED**, **REQUIRES_REVIEW** because the words also appear in the setup panel).  
**Why.** The doctor must see what will change.  
**Feedback.** Current and target use different materials. A legend uses those two words only.  
**Next.** Edit the target, or compare and leave it.

### 17. Tooth labels

**What.** Show `tooth_ref` always. Show FDI only when the pipeline actually produced it.  
**When.** Labels are toggled on, or a tooth is selected.  
**Where.** Viewport labels. **IMPLEMENTED** as DOM labels that can show FDI or a semantic name. The strict “no invented FDI” presentation is **REQUIRES_REVIEW** until the clinical screen is built.  
**Why.** A number that was not established is a false identity.  
**Feedback.** Missing or uncertain teeth are marked review-required, not given a guessed number.  
**Next.** Confirm identity, or leave it as `tooth_ref`.

### 18. Measurement interaction

**What.** Measure a distance the doctor indicates on the model.  
**When.** A measure tool is explicitly on.  
**Where.** Viewport. **PLANNED.** Do not show a permanent measurement form.  
**Why.** Measurements are occasional.  
**Feedback.** The segment and the value appear on the model. Units stay unverified until the case records them.  
**Next.** Clear the measure, or keep it on the tooth note.

### 19. IPR interaction

**What.** Inspect or place interproximal reduction where the plan supports it.  
**When.** Treatment or staging, and both neighboring teeth exist.  
**Where.** On the contact, after those teeth are selected. **PLANNED.** The product must not show a fake zero IPR (**VERIFIED** as a current honesty rule in WP-11).  
**Why.** IPR is a clinical action, not a dashboard count.  
**Feedback.** Amount, neighbors, and requires-review if the value is computed rather than verified.  
**Next.** Undo, or accept into the plan version.

### 20. Attachment interaction

**What.** Inspect or place an attachment on a selected tooth.  
**When.** The plan has an attachment model for that tooth.  
**Where.** On the tooth surface. **PLANNED.**  
**Why.** Attachments are spatial.  
**Feedback.** The attachment is visible on the tooth. Absence is “not placed,” not a fake zero.  
**Next.** Undo, or leave the tooth.

### 21. Validation interaction

**What.** Show findings on the teeth that failed a check.  
**When.** Validation has run.  
**Where.** Viewport color plus one finding list. Geometric validation is **IMPLEMENTED**. A single finding-to-tooth interaction is **PLANNED**.  
**Why.** The doctor should see the problem on the model.  
**Feedback.** Started, working, completed, failed, or requires review. Counts of passed and failed checks stay in that one list.  
**Next.** Select the tooth named by the finding, or open Advanced for the run id.

### 22. Staging interaction

**What.** Scrub the stage while the viewport shows that stage.  
**When.** A staging result exists.  
**Where.** One transport on the viewport. Today both `StagingPanel` and `StageTimeline` can move the stage (**IMPLEMENTED**, **REQUIRES_REVIEW**).  
**Why.** The stage the doctor sees must be the stage they think they are on.  
**Feedback.** Stage index and whether the view is current or target.  
**Next.** Step forward, or return to setup.

### 23. Undo and redo

**What.** Reverse the last doctor edit.  
**When.** An edit was recorded on the session undo stack.  
**Where.** One undo control and `mod+z`. Stack exists in `App.tsx` (**IMPLEMENTED**). It is cleared on case change (**VERIFIED**).  
**Why.** Mistakes must be recoverable where the operation supports it.  
**Feedback.** The model returns to the previous snapshot. If undo is impossible, the control says so.  
**Next.** Redo, or make a new edit.

### 24. Selection persistence

**What.** Keep the same `tooth_ref` selected across stage changes and reloads.  
**When.** The tooth still exists in the next mesh set.  
**Where.** `preserveAcrossTeeth` (**IMPLEMENTED**).  
**Why.** The doctor should not re-find the tooth after a stage scrub.  
**Feedback.** If the tooth disappears, selection clears and the inspector says it is not in this stage.  
**Next.** Select another tooth, or go back a stage.

### 25. Workflow transitions

**What.** Case to Analysis means “understand the scan.” Treatment Plan means “open or create the plan.”  
**When.** The doctor takes the primary action.  
**Where.** One button whose label matches the outcome. **PLANNED.** Today Analyze posts per-arch pipeline work, and Review Treatment Setup posts full processing while the busy text says “Starting case analysis” (**REQUIRES_REVIEW**).  
**Why.** The name must match the job.  
**Feedback.** The step changes only after the job reaches completed, failed, or blocked.  
**Next.** The primary action of the new step.

### 26. Loading and progress

**What.** Show the real phase: segmenting, building the plan, or evaluating collisions.  
**When.** A job is running.  
**Where.** One progress surface. A fullscreen overlay plus side-panel processing rows exist (**IMPLEMENTED**, **REQUIRES_REVIEW**).  
**Why.** A long validation must not look frozen or finished.  
**Feedback.** Started, working, and a phase name. Remaining time only with a real estimate; otherwise “no reliable estimate.”  
**Next.** Wait, or cancel.

### 27. Error feedback

**What.** Say what failed and what the doctor can do.  
**When.** Segmentation, plan, or validation fails.  
**Where.** The step that failed, plus Advanced for the technical string. Wave 1 shows Blocked by environment instead of a clinical tooth count of 0 (**IMPLEMENTED** for that state).  
**Why.** A failure is not an empty success.  
**Feedback.** Failed or blocked, the reason in plain language, and whether it is recoverable.  
**Next.** Retry when the cause can change, or review the scan.

### 28. Recovery feedback

**What.** After cancel or process restart, show cancelled or interrupted, not completed.  
**When.** The user cancels, or the API restarts mid-job.  
**Where.** The same progress surface. WP-13 states are **IMPLEMENTED** and were not changed.  
**Why.** A recovered job must not look successful.  
**Feedback.** Cancelled or interrupted, with the job id in Advanced.  
**Next.** Start a new job. There is no mid-stage resume.

### 29. Information hierarchy

**What.** Level 1 is the seven doctor questions. Level 2 is the selected tooth. Level 3 is Advanced (hashes, model, runtime).  
**When.** Always.  
**Where.** Viewport first, inspector second, Advanced last. **PLANNED.** Analysis still leads with capability matrices (**REQUIRES_REVIEW**).  
**Why.** Technical state that does not change the next action stays hidden.  
**Feedback.** Truth words only: verified, computed, requires review, not available, failed, blocked.  
**Next.** The primary action, or open Advanced.

### 30. Advanced technical information

**What.** Source hash, model version, runtime blocker, validation run id.  
**When.** The doctor or engineer asks.  
**Where.** One Advanced disclosure. **PLANNED** as the only home. Some advanced sections already exist (**IMPLEMENTED** in part).  
**Why.** Provenance stays available without occupying the clinical path.  
**Feedback.** Copy is exact. It does not change clinical truth.  
**Next.** Close Advanced and return to the tooth.

## Segmentation review

Wave 3 builds the review workspace. `tooth_ref` remains the identity when FDI is not authoritative. See `docs/WAVE3_CLINICAL_SEGMENTATION_REVIEW.md`.

## What Wave 2 did not do

Wave 2 did not change layout. Wave 3 did. WP-14 and WP-15 were not started.
