import type { ReviewAttachmentSite, ReviewIPRSite, ProposalStatus } from "../review/types";
import { FixtureBadge } from "./FixtureBadge";

interface ProposalPanelsProps {
  iprSites: readonly ReviewIPRSite[];
  attachmentSites: readonly ReviewAttachmentSite[];
  onIPRStatus: (siteId: string, status: ProposalStatus) => void;
  onIPRAmount: (siteId: string, amount: number) => void;
  onAttachmentStatus: (siteId: string, status: ProposalStatus) => void;
  onReset: () => void;
  readOnly?: boolean;
}

export function ProposalPanels({
  iprSites,
  attachmentSites,
  onIPRStatus,
  onIPRAmount,
  onAttachmentStatus,
  onReset,
  readOnly = false,
}: ProposalPanelsProps): JSX.Element {
  return (
    <section className="proposal-panels">
      <div className="proposal-panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Adjunct proposal</span>
            <h2>
              IPR <span className="count-badge">{iprSites.length}</span>
            </h2>
          </div>
          {readOnly ? (
            <span className="needs-review-label">Review only</span>
          ) : (
            <button className="text-button" onClick={onReset}>
              Reset
            </button>
          )}
        </div>
        {iprSites.length === 0 ? (
          <p className="muted-copy">No determinable interproximal sites.</p>
        ) : (
          iprSites.map((site) => (
            <div className="proposal-row" key={site.siteId}>
              <div className="proposal-row-header">
                <strong>
                  FDI {site.toothA} · FDI {site.toothB}
                </strong>
                <span className={`proposal-status ${site.status}`}>
                  {site.status.replaceAll("_", " ")}
                </span>
              </div>
              <div className="proposal-values">
                <span>Current {site.currentDistance?.toFixed(2) ?? "—"}</span>
                <span>Target {site.targetDistance?.toFixed(2) ?? "—"}</span>
                {readOnly ? (
                  <span>Proposed {site.proposedAmount?.toFixed(2) ?? "—"} mm</span>
                ) : (
                  <label>
                    Proposed{" "}
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={site.proposedAmount ?? ""}
                      onChange={(event) => onIPRAmount(site.siteId, Number(event.target.value))}
                    />{" "}
                    mm
                  </label>
                )}
              </div>
              <p className="proposal-warning">{site.warning}</p>
              <div className="proposal-actions">
                <FixtureBadge fixture={site.fixture} provenance="generated" />
                {!readOnly && (
                  <>
                    <button
                      className="text-button"
                      onClick={() => onIPRStatus(site.siteId, "accepted")}
                    >
                      Accept
                    </button>
                    <button
                      className="text-button danger-text"
                      onClick={() => onIPRStatus(site.siteId, "rejected")}
                    >
                      Reject
                    </button>
                  </>
                )}
              </div>
            </div>
          ))
        )}
      </div>
      <div className="proposal-panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Adjunct proposal</span>
            <h2>
              Attachments <span className="count-badge">{attachmentSites.length}</span>
            </h2>
          </div>
          <span className="needs-review-label">Needs review</span>
        </div>
        {attachmentSites.length === 0 ? (
          <p className="muted-copy">No attachment candidates were generated.</p>
        ) : (
          attachmentSites.map((site) => (
            <div className="proposal-row" key={site.siteId}>
              <div className="proposal-row-header">
                <strong>FDI {site.toothNumber}</strong>
                <span className={`proposal-status ${site.status}`}>
                  {site.status.replaceAll("_", " ")}
                </span>
              </div>
              <div className="proposal-values">
                <span>Type {site.attachmentType}</span>
                <span>Location {site.referencePoint ? "available" : "undetermined"}</span>
              </div>
              <p className="proposal-warning">{site.warning}</p>
              <div className="proposal-actions">
                <FixtureBadge fixture={site.fixture} provenance="generated" />
                {!readOnly && (
                  <>
                    <button
                      className="text-button"
                      onClick={() => onAttachmentStatus(site.siteId, "accepted")}
                    >
                      Accept
                    </button>
                    <button
                      className="text-button danger-text"
                      onClick={() => onAttachmentStatus(site.siteId, "rejected")}
                    >
                      Reject
                    </button>
                  </>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
