"""Deterministic treatment setup generation from explicit objectives."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, replace

import numpy as np

from domain.case.provenance import DataProvenance
from domain.tooth.identification import ToothIdentificationResult
from domain.treatment_plan.input import TreatmentPlanningInput, TreatmentPlanningMode
from domain.treatment_plan.setup import (
    DoctorMovementEdit,
    ProposalKind,
    TargetToothState,
    ToothMovement,
    TreatmentObjective,
    TreatmentPlanProposal,
    TreatmentSetup,
)
from engines.validation.hooks import BasicGeometryValidator


class TreatmentPlanningError(ValueError):
    """Raised for invalid planner configuration or inputs."""


@dataclass(frozen=True)
class TreatmentPlanningEngine:
    """Builds one target setup from explicit, local-frame movements."""

    geometry_validator: BasicGeometryValidator = BasicGeometryValidator()
    engine_version: str = "phase5-setup-1"

    def generate_from_input(
        self,
        case_id: str,
        treatment_input: TreatmentPlanningInput,
        objectives: tuple[TreatmentObjective, ...],
    ) -> TreatmentPlanProposal:
        """Plan from the domain input without depending on segmentation infrastructure."""
        if (
            treatment_input.diagnostics
            and treatment_input.planning_mode is TreatmentPlanningMode.CLINICAL_FDI
        ):
            return self._limited_proposal(
                case_id,
                treatment_input.identification,
                objectives,
                treatment_input.diagnostics,
            )
        return self.generate(
            case_id,
            treatment_input.identification,
            objectives,
            planning_mode=treatment_input.planning_mode,
        )

    def generate(
        self,
        case_id: str,
        identification: ToothIdentificationResult,
        objectives: tuple[TreatmentObjective, ...],
        *,
        planning_mode: TreatmentPlanningMode = TreatmentPlanningMode.CLINICAL_FDI,
    ) -> TreatmentPlanProposal:
        limitations = self._limitations(identification, objectives, planning_mode)
        if limitations:
            return self._limited_proposal(
                case_id, identification, objectives, limitations, planning_mode
            )

        movement_by_tooth: dict[int | str, ToothMovement] = {}
        for objective in sorted(objectives, key=lambda item: item.objective_id):
            for tooth_number, movement in objective.movements:
                movement_by_tooth[tooth_number] = movement_by_tooth.get(
                    tooth_number, ToothMovement()
                ).plus(movement)

        target_states: list[TargetToothState] = []
        source_states: list[TargetToothState] = []
        identified_by_key = {
            self._tooth_key(tooth, planning_mode): tooth
            for tooth in identification.identified
            if self._tooth_key(tooth, planning_mode) is not None
        }
        if planning_mode is TreatmentPlanningMode.SEMANTIC_ONLY_EXPERIMENTAL:
            identified_by_key = {
                tooth.tooth_ref: tooth
                for tooth in identification.teeth
                if tooth.tooth_ref is not None
            }
        for tooth_key in sorted(identified_by_key, key=str):
            tooth = identified_by_key[tooth_key]
            if tooth is None:
                raise TreatmentPlanningError(f"Unknown tooth reference: {tooth_key}")
            if tooth.coordinate_system is None:
                raise TreatmentPlanningError(f"Tooth {tooth_key} has no coordinate system")
            movement = movement_by_tooth.get(tooth_key, ToothMovement())
            source_vertices = tuple(
                tuple(float(value) for value in vertex) for vertex in tooth.instance.mesh_vertices
            )
            if movement.excluded:
                target_vertices = source_vertices
            else:
                target_vertices = self._transform_vertices(
                    source_vertices, tooth.coordinate_system, movement
                )
            state = TargetToothState(
                tooth_number=tooth.identity.number if tooth.identity else None,
                source_instance_id=tooth.instance.instance_id,
                source_vertices=source_vertices,
                source_faces=tooth.instance.mesh_faces,
                target_vertices=target_vertices,
                target_faces=tooth.instance.mesh_faces,
                coordinate_system=tooth.coordinate_system,
                movement=movement,
                provenance=DataProvenance.GENERATED,
                fixture=identification.fixture or tooth.fixture,
                notes="Proposed geometric target; not clinically approved.",
                tooth_ref=tooth.tooth_ref,
                semantic_label=tooth.semantic_label,
                arch=tooth.instance.arch,
                planning_mode=planning_mode.value,
            )
            source_states.append(state)
            target_states.append(state)

        setup = TreatmentSetup(
            source_states=tuple(source_states),
            target_states=tuple(target_states),
            provenance=DataProvenance.GENERATED,
            fixture=identification.fixture,
            assumptions=(
                "Movements are explicit objective inputs expressed in each tooth coordinate frame.",
                "Rigid vertex transformation is a geometric proposal, not a biomechanical claim.",
            ),
            warnings=(
                "No clinical constraints, staging, IPR, attachments, or collision "
                "engine were applied.",
            ),
        )
        findings = self.geometry_validator.validate(setup.target_states)
        warnings = setup.warnings + tuple(finding.message for finding in findings)
        payload = self._canonical_payload(case_id, objectives, setup, warnings)
        plan_id = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        version_id = hashlib.sha256(
            (self.engine_version + ":" + payload).encode("utf-8")
        ).hexdigest()
        return TreatmentPlanProposal(
            plan_id=plan_id,
            version_id=version_id,
            case_id=case_id,
            objectives=tuple(sorted(objectives, key=lambda item: item.objective_id)),
            setup=setup,
            provenance=DataProvenance.GENERATED,
            fixture=identification.fixture,
            assumptions=setup.assumptions,
            warnings=warnings,
            limitations=(),
            planning_mode=planning_mode.value,
        )

    def rebuild_proposal(
        self,
        proposal: TreatmentPlanProposal,
        movement_overrides: dict[int, ToothMovement],
        edit_history: tuple[DoctorMovementEdit, ...],
        proposal_kind: ProposalKind,
    ) -> TreatmentPlanProposal:
        """Rebuild target geometry from source geometry and explicit movements."""
        if proposal.setup is None:
            raise TreatmentPlanningError("Cannot rebuild a proposal without a setup")
        target_states: list[TargetToothState] = []
        known_teeth = {
            state.tooth_ref
            if proposal.planning_mode == "semantic_only_experimental"
            else state.tooth_number
            for state in proposal.setup.source_states
        }
        unknown_teeth = sorted(set(movement_overrides) - known_teeth)
        if unknown_teeth:
            raise TreatmentPlanningError(f"Edit references unknown teeth: {unknown_teeth}")
        for source_state, previous_target in zip(
            proposal.setup.source_states,
            proposal.setup.target_states,
            strict=True,
        ):
            state_key = (
                source_state.tooth_ref
                if proposal.planning_mode == "semantic_only_experimental"
                else source_state.tooth_number
            )
            movement = movement_overrides.get(state_key, previous_target.movement)
            if movement.excluded:
                target_vertices = source_state.source_vertices
            else:
                target_vertices = self._transform_vertices(
                    source_state.source_vertices, source_state.coordinate_system, movement
                )
            target_states.append(
                replace(
                    previous_target,
                    target_vertices=target_vertices,
                    movement=movement,
                )
            )
        setup = replace(proposal.setup, target_states=tuple(target_states))
        extra = {
            "proposal_kind": proposal_kind.value,
            "edit_history": [
                {
                    "edit_id": edit.edit_id,
                    "tooth_number": edit.tooth_number,
                    "previous_movement": edit.previous_movement.__dict__,
                    "new_movement": edit.new_movement.__dict__,
                    "timestamp": edit.timestamp,
                    "version_id": edit.version_id,
                    "provenance": edit.provenance.value,
                    "reason": edit.reason,
                }
                for edit in edit_history
            ],
        }
        payload = self._canonical_payload(proposal.case_id, proposal.objectives, setup, extra)
        plan_id = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        version_id = hashlib.sha256(
            (self.engine_version + ":" + payload).encode("utf-8")
        ).hexdigest()
        return replace(
            proposal,
            plan_id=plan_id,
            version_id=version_id,
            setup=setup,
            proposal_kind=proposal_kind,
            edit_history=edit_history,
            warnings=setup.warnings,
            limitations=(),
        )

    def _limitations(self, identification, objectives, planning_mode):
        limitations: list[str] = []
        if not objectives:
            limitations.append("No explicit treatment objectives were provided.")
        if identification.uncertain and planning_mode is TreatmentPlanningMode.CLINICAL_FDI:
            limitations.append("Uncertain tooth identification prevents setup generation.")
        if identification.unidentified:
            limitations.append("Unidentified tooth geometry prevents setup generation.")
        if planning_mode is TreatmentPlanningMode.SEMANTIC_ONLY_EXPERIMENTAL:
            identified_numbers = {
                tooth.tooth_ref for tooth in identification.teeth if tooth.tooth_ref
            }
        else:
            identified_numbers = {
                tooth.identity.number for tooth in identification.identified if tooth.identity
            }
        requested_numbers = {
            number for objective in objectives for number, _ in objective.movements
        }
        missing = sorted(requested_numbers - identified_numbers)
        if missing:
            if planning_mode is TreatmentPlanningMode.CLINICAL_FDI:
                limitations.append(f"Objectives reference unidentified teeth: {missing}.")
            else:
                limitations.append(f"Objectives reference unknown tooth references: {missing}.")
        return tuple(limitations)

    def _limited_proposal(
        self,
        case_id,
        identification,
        objectives,
        limitations,
        planning_mode=TreatmentPlanningMode.CLINICAL_FDI,
    ):
        payload = self._canonical_payload(case_id, objectives, None, limitations)
        plan_id = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        version_id = hashlib.sha256(
            (self.engine_version + ":" + payload).encode("utf-8")
        ).hexdigest()
        return TreatmentPlanProposal(
            plan_id=plan_id,
            version_id=version_id,
            case_id=case_id,
            objectives=tuple(sorted(objectives, key=lambda item: item.objective_id)),
            setup=None,
            provenance=identification.provenance,
            fixture=identification.fixture,
            assumptions=(),
            warnings=("Planning stopped before target setup generation.",),
            limitations=limitations,
            planning_mode=planning_mode.value,
        )

    @staticmethod
    def _tooth_key(tooth, planning_mode):
        if planning_mode is TreatmentPlanningMode.SEMANTIC_ONLY_EXPERIMENTAL:
            return tooth.tooth_ref
        return tooth.identity.number if tooth.identity else None

    @staticmethod
    def _transform_vertices(vertices, coordinate_system, movement):
        axes = np.asarray(
            [
                coordinate_system.lateral_axis,
                coordinate_system.anterior_axis,
                coordinate_system.vertical_axis,
            ],
            dtype=np.float64,
        )
        origin = np.asarray(coordinate_system.origin, dtype=np.float64)
        local_translation = np.array(
            [movement.translation_x, movement.translation_y, movement.vertical_translation],
            dtype=np.float64,
        )
        translation = local_translation @ axes
        angles = np.radians(
            [movement.lateral_rotation_degrees, movement.torque, movement.rotation]
        )
        rotation = np.eye(3)
        for axis, angle in zip(axes, angles, strict=True):
            skew = np.array(
                [[0.0, -axis[2], axis[1]], [axis[2], 0.0, -axis[0]], [-axis[1], axis[0], 0.0]]
            )
            rotation = (
                np.eye(3) + math.sin(angle) * skew + (1 - math.cos(angle)) * (skew @ skew)
            ) @ rotation
        source = np.asarray(vertices, dtype=np.float64)
        transformed = ((source - origin) @ rotation.T) + origin + translation
        return tuple(tuple(float(value) for value in vertex) for vertex in transformed.tolist())

    def _canonical_payload(self, case_id, objectives, setup, extra):
        def movement_dict(movement):
            return movement.__dict__

        payload = {
            "case_id": case_id,
            "engine_version": self.engine_version,
            "objectives": [
                {
                    "id": objective.objective_id,
                    "type": objective.objective_type.value,
                    "description": objective.description,
                    "assumptions": objective.assumptions,
                    "movements": [
                        (number, movement_dict(movement))
                        for number, movement in objective.movements
                    ],
                }
                for objective in sorted(objectives, key=lambda item: item.objective_id)
            ],
            "setup": None
            if setup is None
            else {
                "targets": [
                    {
                        "tooth_number": state.tooth_number,
                        "source_instance_id": state.source_instance_id,
                        "target_vertices": state.target_vertices,
                    }
                    for state in setup.target_states
                ]
            },
            "extra": extra,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))
