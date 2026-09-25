import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { engineeringFixtureBundle } from "../review/fixtureData";
import { InspectionPanel } from "./InspectionPanel";

describe("InspectionPanel", () => {
  it("shows identity, movement, validation, and fixture state", () => {
    render(<InspectionPanel tooth={engineeringFixtureBundle.stages[0].teeth[0]} />);
    expect(screen.getByRole("heading", { name: "Tooth 11" })).toBeInTheDocument();
    expect(screen.getByText("Move X")).toBeInTheDocument();
    expect(screen.getByText(/FIXTURE/)).toBeInTheDocument();
    expect(screen.getByTestId("current-target-pair")).toBeInTheDocument();
  });
});
