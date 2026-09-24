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
  const boundary = bundle.manufacturingBoundary;

  return (
    <section className="export-panel" aria-label="Export Package">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">Export Package</span>
          <h2>Production QA</h2>
        </div>
        <FixtureBadge fixture={bundle.fixture} provenance={bundle.provenance} />
      </div>
      <div className="export-metrics">
        <div>
          <span>Appliance Stages</span>
          <strong>{bundle.stages.length}</strong>
        </div>
        <div>
          <span>Validation</span>
          <strong>{validationStatus}</strong>
        </div>
        <div>
          <span>IPR / Attachments</span>
          <strong>{proposalStatuses.length === 0 ? "none" : "review"}</strong>
        </div>
        <div>
          <span>Doctor edits</span>
          <strong>{editCount}</strong>
        </div>
      </div>
      <div className="export-audit-summary">
        <span>Package contents</span>
        <small>
          Case metadata · Target Position · Appliance Stages · Validation · IPR Report · Attachment
          Plan · Edit History · provenance · manufacturing boundary
        </small>
      </div>
      {boundary && (
        <div className="export-audit-summary">
          <span>Manufacturing</span>
          <small>
            Shells {boundary.applianceShellGeneration.replaceAll("_", " ")} · Trimline{" "}
            {boundary.trimlineCutline.replaceAll("_", " ")} · QC{" "}
            {boundary.manufacturingQcReport.replaceAll("_", " ")} · Layers separated{" "}
            {boundary.treatmentVsManufacturingSeparated ? "yes" : "no"}
          </small>
        </div>
      )}
      {incomplete && (
        <p className="export-warning">
          Incomplete Export Package: a full treatment session export is not available in this
          workspace yet.
        </p>
      )}
      {warnings.slice(0, 2).map((warning) => (
        <p className="export-warning" key={warning}>
          {warning}
        </p>
      ))}
      <button className="secondary-button export-button" onClick={onExport}>
        Export Package
      </button>
      <p className="muted-copy">
        Export Package is an auditable review artifact and never indicates clinical approval.
        Stage models are treatment geometry, not appliance shells.
      </p>
    </section>
  );
}
