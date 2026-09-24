import type { ReviewBundle } from "../review/types";
import { FixtureBadge } from "./FixtureBadge";

interface ExportPanelProps {
  bundle: ReviewBundle;
  onExport: () => void;
}

export function ExportPanel({ bundle, onExport }: ExportPanelProps): JSX.Element {
  const finalStage = bundle.stages.at(-1);
  const validationStatus = finalStage?.validationStatus ?? "unavailable";
  const proposalStatuses = [...bundle.iprSites, ...bundle.attachmentSites].map(
    (site) => site.status,
  );
  const incomplete = !bundle.realDataAvailable || bundle.stages.length === 0;
  const warnings = [
    ...(bundle.unavailableReason ? [bundle.unavailableReason] : []),
    ...bundle.stages.flatMap((stage) => stage.warnings),
  ];
  const editCount = bundle.editHistory.length;

  return (
    <section className="export-panel" aria-label="Engineering export">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">Engineering export</span>
          <h2>Package readiness</h2>
        </div>
        <FixtureBadge fixture={bundle.fixture} provenance={bundle.provenance} />
      </div>
      <div className="export-metrics">
        <div>
          <span>Stages</span>
          <strong>{bundle.stages.length}</strong>
        </div>
        <div>
          <span>Validation</span>
          <strong>{validationStatus}</strong>
        </div>
        <div>
          <span>Proposals</span>
          <strong>{proposalStatuses.length === 0 ? "none" : "review"}</strong>
        </div>
        <div>
          <span>Doctor edits</span>
          <strong>{editCount}</strong>
        </div>
      </div>
      <div className="export-audit-summary">
        <span>Package contents</span>
        <small>Original metadata · target setup · stages · validation · IPR · attachments · edit history · provenance</small>
      </div>
      {incomplete && (
        <p className="export-warning">
          Incomplete engineering export: the current workspace uses fixture data or lacks a full API
          export bundle.
        </p>
      )}
      {warnings.slice(0, 2).map((warning) => (
        <p className="export-warning" key={warning}>
          {warning}
        </p>
      ))}
      <button className="secondary-button export-button" onClick={onExport}>
        Export ZIP package
      </button>
      <p className="muted-copy">
        Export is an auditable review artifact and never indicates clinical approval.
      </p>
    </section>
  );
}
