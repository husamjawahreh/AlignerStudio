import { describe, expect, it } from "vitest";
import { engineeringFixtureBundle } from "./review/fixtureData";
import {
  applyFixtureMovementEdit,
  cloneMovement,
  hasMovementChanges,
  resetFixtureTooth,
} from "./review/editing";
import { reviewToothKey } from "./viewer/toothKey";
import {
  beginTransformTransaction,
  buildToothInteractionState,
  canTransformTooth,
  movementToSnapshot,
  normalizeClientEditReason,
  resolveConstraintAvailability,
  resolveCoordinateSpace,
  resolvePhase,
  transactionHasChanges,
  updateTransformTransaction,
} from "./viewer/toothInteraction";

describe("WP-04 tooth interaction engine", () => {
  const stage = engineeringFixtureBundle.stages.at(-1)!;
  const tooth = stage.teeth[0];
  const toothKey = reviewToothKey(tooth);

  it("preserves stable tooth identity in interaction state", () => {
    const state = buildToothInteractionState({
      caseId: "case-wp04",
      tooth,
      draft: cloneMovement(tooth.movement),
      base: cloneMovement(tooth.movement),
      selected: true,
      transforming: false,
    });
    expect(state.toothKey).toBe(toothKey);
    expect(state.toothRef).toBe(tooth.toothRef ?? null);
    expect(state.arch).toBe(tooth.arch);
    expect(state.clinicallyApproved).toBe(false);
  });

  it("maps selection to transform target via tooth_ref key", () => {
    const draft = { ...cloneMovement(tooth.movement), translationX: 0.5 };
    const state = buildToothInteractionState({
      caseId: "case-wp04",
      tooth,
      draft,
      base: cloneMovement(tooth.movement),
      selected: true,
      transforming: true,
    });
    expect(state.phase).toBe("actively_transforming");
    expect(state.currentTransform.translationX).toBe(0.5);
    expect(state.baseTransform.translationX).toBe(tooth.movement.translationX);
  });

  it("supports translation, rotation, and combined 6-DOF snapshots", () => {
    const movement = {
      ...cloneMovement(tooth.movement),
      translationX: 0.4,
      translationY: -0.2,
      translationZ: 0.1,
      rotation: 2,
      tip: 1,
      torque: -1.5,
      angulation: 0.5,
      intrusion: 0.05,
      extrusion: 0,
    };
    const snap = movementToSnapshot(movement);
    expect(snap).toEqual({
      translationX: 0.4,
      translationY: -0.2,
      translationZ: 0.1,
      rotation: 2,
      tip: 1,
      torque: -1.5,
      angulation: 0.5,
      intrusion: 0.05,
      extrusion: 0,
    });
  });

  it("blocks transform when locked or excluded", () => {
    expect(canTransformTooth({ ...tooth.movement, locked: true })).toBe(false);
    expect(canTransformTooth({ ...tooth.movement, excluded: true })).toBe(false);
    expect(canTransformTooth(tooth.movement)).toBe(true);
    expect(resolvePhase({ locked: true, excluded: false, selected: true, transforming: true })).toBe(
      "locked",
    );
    expect(resolvePhase({ locked: false, excluded: true, selected: true, transforming: false })).toBe(
      "excluded",
    );
  });

  it("persists lock and exclude through fixture apply path", () => {
    const locked = applyFixtureMovementEdit(
      engineeringFixtureBundle,
      toothKey,
      { ...cloneMovement(tooth.movement), locked: true },
      "2026-09-25T00:00:00Z",
      "doctor_edit",
    );
    const lockedTooth = locked.stages.at(-1)!.teeth.find((item) => reviewToothKey(item) === toothKey)!;
    expect(lockedTooth.movement.locked).toBe(true);
    expect(() =>
      applyFixtureMovementEdit(
        locked,
        toothKey,
        { ...cloneMovement(lockedTooth.movement), translationX: 1, locked: true },
        "2026-09-25T00:00:01Z",
      ),
    ).toThrow(/locked/);

    const excluded = applyFixtureMovementEdit(
      engineeringFixtureBundle,
      toothKey,
      { ...cloneMovement(tooth.movement), excluded: true },
      "2026-09-25T00:00:00Z",
    );
    const excludedTooth = excluded.stages
      .at(-1)!
      .teeth.find((item) => reviewToothKey(item) === toothKey)!;
    expect(excludedTooth.movement.excluded).toBe(true);
    expect(() =>
      applyFixtureMovementEdit(
        excluded,
        toothKey,
        { ...cloneMovement(excludedTooth.movement), translationY: 0.5, excluded: true },
        "2026-09-25T00:00:02Z",
      ),
    ).toThrow(/excluded/);
  });

  it("groups gizmo transforms into one transaction and supports reset", () => {
    const before = cloneMovement(tooth.movement);
    let tx = beginTransformTransaction(toothKey, before, "gizmo_edit");
    tx = updateTransformTransaction(tx, { ...before, translationX: 0.1 });
    tx = updateTransformTransaction(tx, { ...before, translationX: 0.3, rotation: 2 });
    expect(tx.grouped).toBe(true);
    expect(transactionHasChanges(tx)).toBe(true);
    expect(tx.reason).toBe("gizmo_edit");

    const edited = applyFixtureMovementEdit(
      engineeringFixtureBundle,
      toothKey,
      tx.after,
      "2026-09-25T00:00:00Z",
      "gizmo_edit",
    );
    expect(edited.editHistory[0].reason).toBe("gizmo_edit");
    const reset = resetFixtureTooth(edited, toothKey, "2026-09-25T00:00:03Z");
    const resetTooth = reset.stages.at(-1)!.teeth.find((item) => reviewToothKey(item) === toothKey)!;
    expect(hasMovementChanges(resetTooth.movement, before)).toBe(false);
    expect(reset.editHistory[0].reason).toBe("doctor_reset");
  });

  it("records system_restore provenance for undo-style reapply", () => {
    const after = { ...cloneMovement(tooth.movement), translationX: 0.8 };
    const restored = applyFixtureMovementEdit(
      engineeringFixtureBundle,
      toothKey,
      after,
      "2026-09-25T00:00:04Z",
      "system_restore",
    );
    expect(restored.editHistory[0].reason).toBe("system_restore");
  });

  it("exposes constraint availability honestly", () => {
    expect(resolveConstraintAvailability(null)).toBe("unavailable");
    expect(resolveConstraintAvailability("not_configured")).toBe("unavailable");
    expect(resolveConstraintAvailability("exceeded")).toBe("violating");
    expect(resolveConstraintAvailability("within_configured_limit")).toBe("configured");
  });

  it("does not invent clinical local axes from engineering frames", () => {
    expect(resolveCoordinateSpace(tooth)).not.toBe("clinical_local");
    expect(normalizeClientEditReason("ai_generated" as never)).toBe("doctor_edit");
    expect(normalizeClientEditReason("reset")).toBe("doctor_reset");
  });

  it("does not fabricate FDI on fixture teeth without numbers", () => {
    const bare = { ...tooth, fdiNumber: null };
    const state = buildToothInteractionState({
      caseId: "case-wp04",
      tooth: bare,
      draft: cloneMovement(tooth.movement),
      base: cloneMovement(tooth.movement),
      selected: true,
      transforming: false,
    });
    expect(state.fdiNumber).toBeNull();
  });
});
