import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { engineeringFixtureBundle } from "../review/fixtureData";
import { ValidationPanel } from "./ValidationPanel";

describe("ValidationPanel", () => {
  it("shows stage validation counts and warnings", () => {
    render(<ValidationPanel stage={engineeringFixtureBundle.stages[2]} />);
    expect(screen.getByText("Collisions")).toBeInTheDocument();
    expect(
      screen.getByText("Fixture proximity warning for review demonstration."),
    ).toBeInTheDocument();
  });
});
