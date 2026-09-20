"""Deterministic interpolation between a Phase 5 setup source and target."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from domain.treatment_plan.setup import ToothMovement, TreatmentPlanProposal
from domain.treatment_plan.staging import (
    StageMovement,
    StageToothState,
    StagingConfiguration,
    StagingResult,
    TreatmentStage,
)


class TreatmentStagingError(ValueError):
    """Raised for invalid or unavailable staging inputs."""


@dataclass(frozen=True)
class TreatmentStagingEngine:
    """Creates Stage 0, deterministic intermediate states, and final setup."""

    def generate(
        self,
        proposal: TreatmentPlanProposal,
        configuration: StagingConfiguration,
    ) -> StagingResult:
        if proposal.setup is None:
            return self._limited_result(
                proposal,
                configuration,
                ("Treatment plan proposal has no setup to stage.",),
            )
        if proposal.limitations:
            return self._limited_result(proposal, configuration, proposal.limitations)
        if not proposal.setup.source_states or not proposal.setup.target_states:
            return self._limited_result(
                proposal,
                configuration,
                ("Treatment setup contains no tooth states to stage.",),
            )

        source_by_tooth = {state.tooth_number: state for state in proposal.setup.source_states}
        target_by_tooth = {state.tooth_number: state for state in proposal.setup.target_states}
        if set(source_by_tooth) != set(target_by_tooth):
            return self._limited_result(
                proposal,
                configuration,
                ("Treatment setup source and target tooth sets do not match.",),
            )

        stages = tuple(
            self._build_stage(
                proposal,
                configuration,
                source_by_tooth,
                target_by_tooth,
                stage_index,
            )
            for stage_index in range(configuration.stage_count)
        )
        staging_payload = self._canonical_staging_payload(proposal, configuration, stages)
        staging_id = hashlib.sha256(staging_payload.encode("utf-8")).hexdigest()
        return StagingResult(
            plan_id=proposal.plan_id,
            staging_id=staging_id,
            stages=stages,
            provenance=proposal.provenance,
            fixture=proposal.fixture,
            assumptions=(
                "Stage 0 is the immutable source setup.",
                "Intermediate states use deterministic linear interpolation of explicit "
                "movements and vertices.",
                "The final stage copies the Phase 5 target setup exactly.",
            ),
            warnings=(
                "No movement limits, collisions, contacts, IPR, attachments, or clinical "
                "constraints were applied.",
            ),
            limitations=(),
        )

    def _build_stage(
        self,
        proposal,
        configuration,
        source_by_tooth,
        target_by_tooth,
        stage_index,
    ):
        denominator = configuration.stage_count - 1
        progress = stage_index / denominator
        states = []
        for tooth_number in sorted(source_by_tooth):
            source = source_by_tooth[tooth_number]
            target = target_by_tooth[tooth_number]
            if len(source.source_vertices) != len(target.target_vertices):
                raise TreatmentStagingError(
                    f"Tooth {tooth_number} source and target vertex counts differ."
                )
            if stage_index == 0:
                vertices = source.source_vertices
            elif stage_index == denominator:
                vertices = target.target_vertices
            else:
                vertices = tuple(
                    tuple(
                        source.source_vertices[vertex_index][axis]
                        + progress
                        * (
                            target.target_vertices[vertex_index][axis]
                            - source.source_vertices[vertex_index][axis]
                        )
                        for axis in range(3)
                    )
                    for vertex_index in range(len(source.source_vertices))
                )
            movement = self._scale_movement(target.movement, progress)
            states.append(
                StageToothState(
                    tooth_number=tooth_number,
                    source_instance_id=source.source_instance_id,
                    source_vertices=source.source_vertices,
                    source_faces=source.source_faces,
                    final_target_vertices=target.target_vertices,
                    final_target_faces=target.target_faces,
                    vertices=vertices,
                    coordinate_system=target.coordinate_system,
                    movement=StageMovement(tooth_number, movement, progress),
                    provenance=target.provenance,
                    fixture=target.fixture,
                    notes=(
                        "Stage 0 source or deterministic interpolated proposal; "
                        "not clinically approved."
                    ),
                )
            )
        stage_payload = self._canonical_stage_payload(stage_index, states)
        stage_hash = hashlib.sha256(stage_payload.encode("utf-8")).hexdigest()
        stage_id = hashlib.sha256(
            f"{proposal.plan_id}:{configuration.engine_version}:{stage_index}:{stage_hash}".encode()
        ).hexdigest()
        return TreatmentStage(
            stage_index=stage_index,
            stage_id=stage_id,
            tooth_states=tuple(states),
            provenance=proposal.provenance,
            fixture=proposal.fixture,
            stage_hash=stage_hash,
            notes="Deterministic geometric stage; no clinical approval implied.",
        )

    @staticmethod
    def _scale_movement(movement: ToothMovement, progress: float) -> ToothMovement:
        values = {
            field: getattr(movement, field) * progress
            for field in (
                "translation_x",
                "translation_y",
                "translation_z",
                "rotation",
                "tip",
                "torque",
                "intrusion",
                "extrusion",
            )
        }
        return ToothMovement(**values)

    def _limited_result(self, proposal, configuration, limitations):
        payload = json.dumps(
            {
                "plan_id": proposal.plan_id,
                "engine_version": configuration.engine_version,
                "stage_count": configuration.stage_count,
                "limitations": tuple(limitations),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return StagingResult(
            plan_id=proposal.plan_id,
            staging_id=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
            stages=(),
            provenance=proposal.provenance,
            fixture=proposal.fixture,
            assumptions=(),
            warnings=("Staging stopped without modifying the treatment proposal.",),
            limitations=tuple(limitations),
        )

    @staticmethod
    def _canonical_stage_payload(stage_index, states):
        return json.dumps(
            {
                "stage_index": stage_index,
                "states": [
                    {
                        "tooth_number": state.tooth_number,
                        "source_instance_id": state.source_instance_id,
                        "vertices": state.vertices,
                        "movement": state.movement.movement.__dict__,
                        "progress": state.movement.progress,
                    }
                    for state in states
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    def _canonical_staging_payload(self, proposal, configuration, stages):
        return json.dumps(
            {
                "plan_id": proposal.plan_id,
                "engine_version": configuration.engine_version,
                "stages": [
                    {
                        "index": stage.stage_index,
                        "id": stage.stage_id,
                        "hash": stage.stage_hash,
                    }
                    for stage in stages
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
