import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { engineeringFixtureBundle } from "../review/fixtureData";
import { ProposalPanels } from "./ProposalPanels";

describe("ProposalPanels", () => {
  it("shows IPR and attachment proposals with review warnings", () => {
    render(
      <ProposalPanels
        iprSites={engineeringFixtureBundle.iprSites}
        attachmentSites={engineeringFixtureBundle.attachmentSites}
        onIPRStatus={vi.fn()}
        onIPRAmount={vi.fn()}
        onAttachmentStatus={vi.fn()}
        onReset={vi.fn()}
      />,
    );
    expect(screen.getByText("IPR review")).toBeInTheDocument();
    expect(screen.getByText("Attachments")).toBeInTheDocument();
    expect(screen.getAllByText(/not a clinical/).length).toBeGreaterThan(0);
    expect(screen.getByText(/dimensions require doctor review/)).toBeInTheDocument();
  });
});
