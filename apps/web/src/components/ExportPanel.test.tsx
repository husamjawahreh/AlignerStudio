import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { engineeringFixtureBundle } from "../review/fixtureData";
import { ExportPanel } from "./ExportPanel";

describe("ExportPanel", () => {
  it("labels fixture exports as incomplete and invokes the export action", async () => {
    const onExport = vi.fn();
    render(<ExportPanel bundle={engineeringFixtureBundle} onExport={onExport} />);
    expect(screen.getByText(/Incomplete Export Package/)).toBeInTheDocument();
    screen.getByRole("button", { name: "Export Package" }).click();
    expect(onExport).toHaveBeenCalledOnce();
  });
});
