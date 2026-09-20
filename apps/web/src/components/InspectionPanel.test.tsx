import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { engineeringFixtureBundle } from "../review/fixtureData";
import { InspectionPanel } from "./InspectionPanel";

describe("InspectionPanel", () => {
  it("shows identity, movement, validation, and fixture state", () => {
    render(<InspectionPanel tooth={engineeringFixtureBundle.stages[0].teeth[0]} />);
    expect(screen.getByText("FDI 11")).toBeInTheDocument();
    expect(screen.getByText("Translation X")).toBeInTheDocument();
    expect(screen.getByText(/FIXTURE/)).toBeInTheDocument();
  });
});
