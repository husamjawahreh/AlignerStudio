import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ContextualToothToolbar } from "./ContextualToothToolbar";

describe("ContextualToothToolbar", () => {
  it("wires live callbacks for gizmo, overlays, and edit actions", () => {
    const onGizmoMode = vi.fn();
    const onToggleTargetGhost = vi.fn();
    const onApply = vi.fn();
    const onClearSelection = vi.fn();

    render(
      <ContextualToothToolbar
        label="FDI 11"
        arch="upper"
        gizmoMode="translate"
        onGizmoMode={onGizmoMode}
        canEdit
        isDirty
        locked={false}
        excluded={false}
        showTargetGhost
        targetGhostAvailable
        showMovementVectors={false}
        onToggleTargetGhost={onToggleTargetGhost}
        onToggleMovementVectors={vi.fn()}
        onToggleLocked={vi.fn()}
        onToggleExcluded={vi.fn()}
        onApply={onApply}
        onCancel={vi.fn()}
        onClearSelection={onClearSelection}
      />,
    );

    expect(screen.getByTestId("contextual-tooth-toolbar")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Rotate" }));
    expect(onGizmoMode).toHaveBeenCalledWith("rotate");
    fireEvent.click(screen.getByRole("button", { name: "Target" }));
    expect(onToggleTargetGhost).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(onApply).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(onClearSelection).toHaveBeenCalled();
  });

  it("disables edit actions when the selection cannot be edited", () => {
    render(
      <ContextualToothToolbar
        label="Semantic tooth"
        arch="lower"
        gizmoMode="translate"
        onGizmoMode={vi.fn()}
        canEdit={false}
        isDirty={false}
        locked={false}
        excluded={false}
        showTargetGhost={false}
        targetGhostAvailable={false}
        showMovementVectors
        onToggleTargetGhost={vi.fn()}
        onToggleMovementVectors={vi.fn()}
        onToggleLocked={vi.fn()}
        onToggleExcluded={vi.fn()}
        onApply={vi.fn()}
        onCancel={vi.fn()}
        onClearSelection={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: "Apply" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Move" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Target" })).toBeDisabled();
  });
});
