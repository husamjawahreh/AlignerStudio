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
  clinicalToolsFreshness?: string;
  clinicalToolsNotes?: readonly string[];
}

function formatIdentity(value: number | string): string {
  return typeof value === "number" ? `FDI ${value}` : String(value);
}

function formatAmount(value: number | null | undefined, unit: string): string {
  if (value === null || value === undefined) return "Not available";
  return `${value.toFixed(2)} ${unit}`;
}

export function ProposalPanels({
  iprSites,
  attachmentSites,
  onIPRStatus,
  onIPRAmount,
  onAttachmentStatus,
  onReset,
  readOnly = false,
  clinicalToolsFreshness,
  clinicalToolsNotes = [],
}: ProposalPanelsProps): JSX.Element {
  return (
    <section className="proposal-panels">
      <div className="proposal-panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Clinical tool · review required</span>
            <h2>
              IPR{" "}
              <span className="count-badge">
                {iprSites.length === 0 ? "n/a" : iprSites.length}
              </span>
            </h2>
          </div>
          {readOnly ? (
            <span className="needs-review-label">Review only</span>
          ) : (
            <button className="text-button" onClick={onReset}>
              Regenerate
            </button>
          )}
        </div>
        {clinicalToolsFreshness === "stale" && (
          <p className="proposal-warning">Stale relative to setup/staging — regenerate required.</p>
        )}
        {iprSites.length === 0 ? (
          <p className="muted-copy" data-testid="ipr-empty-state">
            Not available — no determinable interproximal sites from current geometry. An empty
            list does not mean IPR is unnecessary.
          </p>
        ) : (
          iprSites.map((site) => {
            const unit = site.amountUnit ?? "model units";
            return (
              <div className="proposal-row" key={site.siteId}>
                <div className="proposal-row-header">
                  <strong>
                    {formatIdentity(site.toothA)} · {formatIdentity(site.toothB)}
                  </strong>
                  <span className={`proposal-status ${site.status}`}>
                    {site.status.replaceAll("_", " ")}
                  </span>
                </div>
                <div className="proposal-values">
                  <span>
                    Measured {formatAmount(site.measuredAmount ?? site.currentDistance, unit)}
                  </span>
                  <span>
                    Computed proposal{" "}
                    {formatAmount(
                      site.computedProposalAmount ??
                        (site.valueSource === "doctor_entered" ? null : site.proposedAmount),
                      unit,
                    )}
                  </span>
                  <span>
                    Doctor entered{" "}
                    {site.doctorEnteredAmount != null
                      ? formatAmount(site.doctorEnteredAmount, unit)
                      : "—"}
                  </span>
                  {readOnly ? (
                    <span>
                      Active {formatAmount(site.proposedAmount, unit)}
                    </span>
                  ) : (
                    <label>
                      Active{" "}
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={site.proposedAmount ?? ""}
                        onChange={(event) =>
                          onIPRAmount(site.siteId, Number(event.target.value))
                        }
                      />{" "}
                      {unit}
                    </label>
                  )}
                  <span>Truth {site.truthState?.replaceAll("_", " ") ?? "requires review"}</span>
                  <span>Source {site.valueSource?.replaceAll("_", " ") ?? "unknown"}</span>
                  <span>
                    Stage{" "}
                    {site.stage === null || site.stage === undefined ? "unassigned" : site.stage}
                  </span>
                </div>
                <p className="proposal-warning">{site.warning}</p>
                {site.limitations?.length ? (
                  <small className="cad-review-note">{site.limitations[0]}</small>
                ) : null}
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
            );
          })
        )}
      </div>
      <div className="proposal-panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Clinical tool · review required</span>
            <h2>
              Attachments{" "}
              <span className="count-badge">
                {attachmentSites.length === 0 ? "n/a" : attachmentSites.length}
              </span>
            </h2>
          </div>
          <span className="needs-review-label">Needs review</span>
        </div>
        {attachmentSites.length === 0 ? (
          <p className="muted-copy" data-testid="attachments-empty-state">
            Not available — no attachment candidates were generated. An empty list does not prove
            attachments are unnecessary.
          </p>
        ) : (
          attachmentSites.map((site) => (
            <div className="proposal-row" key={site.siteId}>
              <div className="proposal-row-header">
                <strong>{formatIdentity(site.toothNumber)}</strong>
                <span className={`proposal-status ${site.status}`}>
                  {site.status.replaceAll("_", " ")}
                </span>
              </div>
              <div className="proposal-values">
                <span>Type {site.attachmentType}</span>
                <span>Location {site.referencePoint ? "available" : "undetermined"}</span>
                <span>
                  Dimensions{" "}
                  {site.dimensions
                    ? site.dimensions.map((value) => value.toFixed(2)).join(" × ")
                    : "Not available"}
                </span>
                <span>Truth {site.truthState?.replaceAll("_", " ") ?? "requires review"}</span>
                <span>
                  Stage{" "}
                  {site.stage === null || site.stage === undefined ? "unassigned" : site.stage}
                </span>
                <span>Generated {site.generated ? "yes" : "no"}</span>
              </div>
              <p className="proposal-warning">{site.warning}</p>
              {site.limitations?.length ? (
                <small className="cad-review-note">{site.limitations[0]}</small>
              ) : null}
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
        {clinicalToolsNotes.length > 0 && (
          <small className="cad-review-note">{clinicalToolsNotes[0]}</small>
        )}
      </div>
    </section>
  );
}
