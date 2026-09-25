import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  Button,
  ConfirmDialog,
  EmptyState,
  SegmentedControl,
  StatusBadge,
  TruthBadge,
  fdiTruthPresentation,
  truthFromProvenance,
  FORBIDDEN_DOCTOR_TERMS,
  matchCommandShortcut,
} from "./index";

describe("design-system truth states", () => {
  it("maps fixture/experimental provenance to Requires Review — never Verified", () => {
    expect(truthFromProvenance({ fixture: true }).state).toBe("requires_review");
    expect(truthFromProvenance({ experimental: true }).state).toBe("requires_review");
    expect(truthFromProvenance({ provenance: "clinically_reviewed" }).state).toBe("verified");
    expect(truthFromProvenance({ available: false }).state).toBe("not_available");
  });

  it("never fabricates FDI truth", () => {
    expect(fdiTruthPresentation(null).state).toBe("not_available");
    expect(fdiTruthPresentation(11).state).toBe("computed");
    expect(fdiTruthPresentation(11).reason).toMatch(/FDI 11/);
  });

  it("renders truth badge labels for all four states", () => {
    const { rerender } = render(<TruthBadge state="verified" />);
    expect(screen.getByText("Verified")).toBeInTheDocument();
    rerender(<TruthBadge state="computed" />);
    expect(screen.getByText("Computed")).toBeInTheDocument();
    rerender(<TruthBadge state="requires_review" />);
    expect(screen.getByText("Requires Review")).toBeInTheDocument();
    rerender(<TruthBadge state="not_available" reason="No landmarks" />);
    expect(screen.getByText("Not Available")).toBeInTheDocument();
    expect(screen.getByText("No landmarks")).toBeInTheDocument();
  });

  it("keeps forbidden engineering terms out of truth labels", () => {
    const labels = [
      truthFromProvenance({ fixture: true }).label,
      truthFromProvenance({ available: false }).label,
      fdiTruthPresentation(null).label,
    ];
    for (const term of FORBIDDEN_DOCTOR_TERMS) {
      for (const label of labels) {
        expect(label.toLowerCase()).not.toContain(term.toLowerCase());
      }
    }
  });
});

describe("design-system primitives", () => {
  it("renders button, segmented control, status badge, and empty state", () => {
    render(
      <>
        <Button variant="primary">Analyze</Button>
        <SegmentedControl
          ariaLabel="Arch"
          value="upper"
          options={[
            { value: "upper", label: "Upper" },
            { value: "lower", label: "Lower" },
          ]}
          onChange={() => undefined}
        />
        <StatusBadge tone="warning">Requires Review</StatusBadge>
        <EmptyState title="No case" message="Import upper and lower scans to begin." />
      </>,
    );
    expect(screen.getByRole("button", { name: "Analyze" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Arch" })).toBeInTheDocument();
    expect(screen.getByText("No case")).toBeInTheDocument();
  });

  it("renders confirmation dialog only when open", () => {
    const { rerender } = render(
      <ConfirmDialog
        open={false}
        title="Cancel analysis?"
        message="Progress will be discarded."
        onConfirm={() => undefined}
        onCancel={() => undefined}
      />,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    rerender(
      <ConfirmDialog
        open
        title="Cancel analysis?"
        message="Progress will be discarded."
        onConfirm={() => undefined}
        onCancel={() => undefined}
      />,
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("matches command shortcuts", () => {
    const run = vi.fn();
    const hit = matchCommandShortcut(
      { key: "z", metaKey: true, ctrlKey: false, altKey: false, shiftKey: false },
      [{ id: "undo", label: "Undo", shortcut: "mod+z", run }],
    );
    expect(hit?.id).toBe("undo");
  });
});
