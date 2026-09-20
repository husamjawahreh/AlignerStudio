import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FixtureBadge } from "./FixtureBadge";

describe("FixtureBadge", () => {
  it("visibly flags fixture data", () => {
    render(<FixtureBadge fixture={true} provenance="generated" notes="test note" />);
    expect(screen.getByText(/FIXTURE/)).toBeInTheDocument();
    expect(screen.getByText("test note")).toBeInTheDocument();
  });

  it("does not flag real, non-fixture data as a fixture", () => {
    render(<FixtureBadge fixture={false} provenance="real" />);
    expect(screen.queryByText(/FIXTURE/)).not.toBeInTheDocument();
  });
});
