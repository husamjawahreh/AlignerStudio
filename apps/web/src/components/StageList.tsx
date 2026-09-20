import type { TreatmentPlan } from "@alignerstudio/contracts";
import { FixtureBadge } from "./FixtureBadge";

interface StageListProps {
  plan: TreatmentPlan;
}

export function StageList({ plan }: StageListProps): JSX.Element {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <FixtureBadge fixture={plan.fixture} provenance={plan.provenance} notes={plan.notes} />
      <ol style={{ margin: 0, paddingLeft: 20 }}>
        {plan.stages.map((stage) => (
          <li key={stage.index} style={{ marginBottom: 8 }}>
            <div>
              Stage {stage.index} — {stage.tooth_positions.length} teeth
            </div>
            <FixtureBadge
              fixture={stage.fixture}
              provenance={stage.provenance}
              notes={stage.notes}
            />
          </li>
        ))}
      </ol>
    </div>
  );
}
