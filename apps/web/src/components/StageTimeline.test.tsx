import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { engineeringFixtureBundle } from "../review/fixtureData";
import { StageTimeline } from "./StageTimeline";

describe("StageTimeline", () => {
  it("selects stages and exposes play controls", () => {
    const onSelect = vi.fn();
    render(
      <StageTimeline
        stages={engineeringFixtureBundle.stages}
        selectedIndex={0}
        isPlaying={false}
        onSelect={onSelect}
        onPrevious={vi.fn()}
        onNext={vi.fn()}
        onTogglePlay={vi.fn()}
      />,
    );
    screen.getByRole("button", { name: "Next stage" }).click();
    expect(screen.getByRole("button", { name: "Play stages" })).toBeInTheDocument();
  });
});
