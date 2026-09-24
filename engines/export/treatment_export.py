"""Phase 11 deterministic engineering export for immutable treatment-plan artifacts."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import shutil
import zipfile
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from domain.case.provenance import DataProvenance
from domain.treatment_plan.proposals import TreatmentProposalResult
from domain.treatment_plan.setup import TreatmentPlanProposal
from domain.treatment_plan.staging import StagingResult, TreatmentStage
from domain.treatment_plan.validation import TreatmentValidationReport


class TreatmentExportError(ValueError):
    """Raised when an export bundle is incomplete or internally inconsistent."""


def _tooth_identity_key(state: Any) -> int | str:
    """FDI when genuinely present; otherwise authoritative semantic tooth_ref. Never invent FDI."""
    tooth_number = getattr(state, "tooth_number", None)
    if tooth_number is not None:
        return tooth_number
    tooth_ref = getattr(state, "tooth_ref", None)
    if tooth_ref:
        return tooth_ref
    raise TreatmentExportError("Tooth state is missing both tooth_number and tooth_ref")


@dataclass(frozen=True)
class TreatmentExportPackage:
    """Locations and immutable identifiers for a completed engineering export."""

    root: Path
    zip_path: Path
    manifest_path: Path
    manifest_hash: str
    files: tuple[str, ...]
    incomplete: bool


@dataclass(frozen=True)
class TreatmentExportEngine:
    """Exports already-computed plans without interpreting or modifying them."""

    software_version: str = "phase11-export-1"

    def export(
        self,
        destination: Path,
        plan: TreatmentPlanProposal,
        staging: StagingResult,
        validation: TreatmentValidationReport,
        proposals: TreatmentProposalResult,
        *,
        export_timestamp: str | None = None,
        allow_incomplete: bool = False,
    ) -> TreatmentExportPackage:
        """Validate and write one self-contained, review-only export package."""
        issues = self._validate_bundle(plan, staging, validation, proposals)
        if issues and not allow_incomplete:
            raise TreatmentExportError("Export validation failed: " + "; ".join(issues))

        timestamp = export_timestamp or datetime.now(timezone.utc).isoformat()
        root = Path(destination)
        if root.exists():
            shutil.rmtree(root)
        (root / "stages").mkdir(parents=True)
        (root / "reports").mkdir()

        incomplete = bool(issues)
        status = self._export_status(plan, staging, validation, proposals)
        context = self._context(plan, staging, validation, proposals, status, incomplete, issues)
        artifacts = self._artifact_bytes(plan, staging, validation, proposals, context)
        for relative_path, content in artifacts.items():
            target = root / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)

        file_hashes = {
            relative_path: self._sha256(content)
            for relative_path, content in sorted(artifacts.items())
        }
        manifest = {
            **context,
            "export_timestamp": timestamp,
            "files": [{"path": path, "sha256": digest} for path, digest in file_hashes.items()],
            "manifest_hash_scope": "Canonical manifest content excluding manifest_hash.",
        }
        manifest_hash = self._sha256(self._json_bytes(manifest))
        manifest["manifest_hash"] = manifest_hash
        manifest_path = root / "manifest.json"
        manifest_path.write_bytes(self._json_bytes(manifest))
        zip_path = root.with_suffix(".zip")
        self._write_zip(root, zip_path)
        return TreatmentExportPackage(
            root=root,
            zip_path=zip_path,
            manifest_path=manifest_path,
            manifest_hash=manifest_hash,
            files=tuple(sorted((*artifacts, "manifest.json"))),
            incomplete=incomplete,
        )

    def _validate_bundle(
        self,
        plan: TreatmentPlanProposal,
        staging: StagingResult,
        validation: TreatmentValidationReport,
        proposals: TreatmentProposalResult,
    ) -> tuple[str, ...]:
        issues: list[str] = []
        if plan.setup is None:
            issues.append("treatment plan has no setup")
        if plan.limitations:
            issues.append("treatment plan has limitations")
        if not staging.stages:
            issues.append("staging has no stages")
        if staging.plan_id != plan.plan_id:
            issues.append("staging plan ID does not match treatment plan")
        if validation.plan_id != plan.plan_id:
            issues.append("validation plan ID does not match treatment plan")
        if proposals.plan_id != plan.plan_id or proposals.version_id != plan.version_id:
            issues.append("adjunct proposals do not reference the treatment plan version")
        if proposals.ipr.plan_id != plan.plan_id or proposals.ipr.version_id != plan.version_id:
            issues.append("IPR proposal reference is inconsistent")
        if (
            proposals.attachments.plan_id != plan.plan_id
            or proposals.attachments.version_id != plan.version_id
        ):
            issues.append("attachment proposal reference is inconsistent")
        if not all(
            isinstance(value, DataProvenance)
            for value in (
                plan.provenance,
                staging.provenance,
                validation.provenance,
                proposals.provenance,
            )
        ):
            issues.append("export provenance is incomplete")
        if staging.stages:
            expected_indexes = list(range(len(staging.stages)))
            actual_indexes = [stage.stage_index for stage in staging.stages]
            if actual_indexes != expected_indexes:
                issues.append("stage indexes are not contiguous and ordered")
            validation_ids = {result.stage_id for result in validation.stage_results}
            for stage in staging.stages:
                if not stage.stage_id:
                    issues.append(f"stage {stage.stage_index} has no stable ID")
                if stage.stage_id not in validation_ids:
                    issues.append(f"stage {stage.stage_index} is absent from validation")
                issues.extend(self._mesh_issues(stage))
            if plan.setup is not None:
                first = staging.stages[0]
                final = staging.stages[-1]
                source = {_tooth_identity_key(item): item for item in plan.setup.source_states}
                target = {_tooth_identity_key(item): item for item in plan.setup.target_states}
                if {_tooth_identity_key(item) for item in first.tooth_states} != set(source):
                    issues.append("Stage 0 tooth references do not match source setup")
                if {_tooth_identity_key(item) for item in final.tooth_states} != set(target):
                    issues.append("final stage tooth references do not match target setup")
                for state in first.tooth_states:
                    key = _tooth_identity_key(state)
                    if state.vertices != source[key].source_vertices:
                        issues.append(f"Stage 0 differs from source geometry for tooth {key}")
                for state in final.tooth_states:
                    key = _tooth_identity_key(state)
                    if state.vertices != target[key].target_vertices:
                        issues.append(
                            f"final stage differs from target geometry for tooth {key}"
                        )
        return tuple(sorted(set(issues)))

    @staticmethod
    def _mesh_issues(stage: TreatmentStage) -> list[str]:
        issues: list[str] = []
        for state in stage.tooth_states:
            tooth_key = _tooth_identity_key(state)
            if not state.vertices or not state.final_target_faces:
                issues.append(f"stage {stage.stage_index} tooth {tooth_key} has empty mesh")
                continue
            if not all(math.isfinite(value) for vertex in state.vertices for value in vertex):
                issues.append(
                    f"stage {stage.stage_index} tooth {tooth_key} has non-finite vertices"
                )
            if any(
                min(face) < 0 or max(face) >= len(state.vertices)
                for face in state.final_target_faces
            ):
                issues.append(
                    f"stage {stage.stage_index} tooth {tooth_key} has invalid face indexes"
                )
        return issues

    def _artifact_bytes(
        self,
        plan: TreatmentPlanProposal,
        staging: StagingResult,
        validation: TreatmentValidationReport,
        proposals: TreatmentProposalResult,
        context: dict[str, Any],
    ) -> dict[str, bytes]:
        report_context = {"export": context}
        artifacts = {
            "treatment-plan.json": self._json_bytes(
                {**report_context, "treatment_plan": self._plain(plan)}
            ),
            "reports/movements.json": self._json_bytes(
                {**report_context, "movements": self._movements(staging)}
            ),
            "reports/movements.csv": self._movement_csv(staging),
            "reports/staging.json": self._json_bytes(
                {**report_context, "staging": self._plain(staging)}
            ),
            "reports/validation.json": self._json_bytes(
                {**report_context, "validation": self._plain(validation)}
            ),
            "reports/ipr.json": self._json_bytes(
                {**report_context, "ipr": self._plain(proposals.ipr)}
            ),
            "reports/attachments.json": self._json_bytes(
                {**report_context, "attachments": self._plain(proposals.attachments)}
            ),
            "reports/edit-history.json": self._json_bytes(
                {**report_context, "edit_history": self._plain(plan.edit_history)}
            ),
            "reports/provenance.json": self._json_bytes(
                {**report_context, "provenance": context["provenance"]}
            ),
        }
        artifacts.update(
            {
                f"stages/stage-{stage.stage_index:03d}.stl": self._stage_stl(stage)
                for stage in staging.stages
            }
        )
        return artifacts

    def _context(self, plan, staging, validation, proposals, status, incomplete, issues):
        from domain.treatment_plan.manufacturing import build_manufacturing_boundary_report

        manufacturing = build_manufacturing_boundary_report(
            has_stage_models=bool(staging.stages)
        )
        return {
            "case_id": plan.case_id,
            "treatment_plan_id": plan.plan_id,
            "plan_version": plan.version_id,
            "staging_hash": staging.staging_id,
            "validation_hash": validation.report_id,
            "software_version": self.software_version,
            "package_kind": manufacturing.package_kind,
            "artifact_layers": {
                "treatment_design": "included",
                "geometric_validation": "included",
                "manufacturing_preparation": manufacturing.appliance_shell_generation.value,
                "manufacturing_validation": manufacturing.manufacturing_qc_report.value,
            },
            "manufacturing_boundary": manufacturing.payload(),
            "provenance": {
                "plan": plan.provenance.value,
                "staging": staging.provenance.value,
                "validation": validation.provenance.value,
                "proposals": proposals.provenance.value,
            },
            "data_status": status,
            "fixture": plan.fixture or staging.fixture or validation.fixture or proposals.fixture,
            "incomplete_engineering_export": incomplete,
            "warnings": list(issues),
            "clinical_approval": False,
        }

    def verify_package(self, zip_path: Path) -> dict[str, Any]:
        """Re-open an export ZIP and verify file hashes against the manifest.

        Does not invent manufacturing geometry. Returns an auditable verification report.
        """
        zip_path = Path(zip_path)
        if not zip_path.exists():
            raise TreatmentExportError(f"Export package not found: {zip_path}")
        with zipfile.ZipFile(zip_path, "r") as archive:
            names = set(archive.namelist())
            if "manifest.json" not in names:
                raise TreatmentExportError("Export package is missing manifest.json")
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            expected_hash = manifest.get("manifest_hash")
            files = manifest.get("files", [])
            mismatches: list[str] = []
            missing: list[str] = []
            for entry in files:
                path = entry["path"]
                expected = entry["sha256"]
                if path not in names:
                    missing.append(path)
                    continue
                digest = self._sha256(archive.read(path))
                if digest != expected:
                    mismatches.append(path)
            content_for_hash = {
                key: value for key, value in manifest.items() if key != "manifest_hash"
            }
            recomputed = self._sha256(self._json_bytes(content_for_hash))
            manifest_ok = recomputed == expected_hash
            return {
                "verified": manifest_ok and not mismatches and not missing,
                "manifest_hash_matches": manifest_ok,
                "missing_files": missing,
                "hash_mismatches": mismatches,
                "package_kind": manifest.get("package_kind"),
                "treatment_plan_id": manifest.get("treatment_plan_id"),
                "plan_version": manifest.get("plan_version"),
                "manufacturing_boundary": manifest.get("manufacturing_boundary"),
                "clinical_approval": manifest.get("clinical_approval", False),
            }

    @staticmethod
    def _export_status(plan, staging, validation, proposals) -> str:
        values = {plan.provenance, staging.provenance, validation.provenance, proposals.provenance}
        if DataProvenance.FIXTURE in values or any(
            (plan.fixture, staging.fixture, validation.fixture, proposals.fixture)
        ):
            return DataProvenance.FIXTURE.value
        if DataProvenance.EXPERIMENTAL in values:
            return DataProvenance.EXPERIMENTAL.value
        if DataProvenance.GENERATED in values:
            return DataProvenance.GENERATED.value
        return DataProvenance.REAL.value

    @staticmethod
    def _movements(staging: StagingResult) -> list[dict[str, Any]]:
        return [
            {
                "stage_index": stage.stage_index,
                "stage_id": stage.stage_id,
                "tooth_number": state.tooth_number,
                "tooth_ref": state.tooth_ref,
                "tooth_key": _tooth_identity_key(state),
                **TreatmentExportEngine._plain(state.movement.movement),
                "progress": state.movement.progress,
            }
            for stage in staging.stages
            for state in stage.tooth_states
        ]

    @staticmethod
    def _movement_csv(staging: StagingResult) -> bytes:
        output = io.StringIO(newline="")
        fields = [
            "stage_index",
            "stage_id",
            "tooth_number",
            "tooth_ref",
            "tooth_key",
            "progress",
            "translation_x",
            "translation_y",
            "translation_z",
            "rotation",
            "tip",
            "torque",
            "angulation",
            "intrusion",
            "extrusion",
            "locked",
            "excluded",
        ]
        writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(TreatmentExportEngine._movements(staging))
        return output.getvalue().encode("utf-8")

    @staticmethod
    def _stage_stl(stage: TreatmentStage) -> bytes:
        lines = [f"solid stage-{stage.stage_index:03d}-{stage.stage_id}"]
        for state in sorted(stage.tooth_states, key=lambda item: str(_tooth_identity_key(item))):
            for face in state.final_target_faces:
                first, second, third = (state.vertices[index] for index in face)
                normal = TreatmentExportEngine._normal(first, second, third)
                lines.extend(
                    [
                        f"  facet normal {normal[0]:.17g} {normal[1]:.17g} {normal[2]:.17g}",
                        "    outer loop",
                        f"      vertex {first[0]:.17g} {first[1]:.17g} {first[2]:.17g}",
                        f"      vertex {second[0]:.17g} {second[1]:.17g} {second[2]:.17g}",
                        f"      vertex {third[0]:.17g} {third[1]:.17g} {third[2]:.17g}",
                        "    endloop",
                        "  endfacet",
                    ]
                )
        lines.append(f"endsolid stage-{stage.stage_index:03d}-{stage.stage_id}")
        return ("\n".join(lines) + "\n").encode("ascii")

    @staticmethod
    def _normal(first, second, third) -> tuple[float, float, float]:
        ab = tuple(second[index] - first[index] for index in range(3))
        ac = tuple(third[index] - first[index] for index in range(3))
        normal = (
            ab[1] * ac[2] - ab[2] * ac[1],
            ab[2] * ac[0] - ab[0] * ac[2],
            ab[0] * ac[1] - ab[1] * ac[0],
        )
        length = math.sqrt(sum(value * value for value in normal))
        return (0.0, 0.0, 0.0) if length == 0.0 else tuple(value / length for value in normal)

    @staticmethod
    def _plain(value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        if is_dataclass(value):
            return TreatmentExportEngine._plain(asdict(value))
        if isinstance(value, dict):
            return {str(key): TreatmentExportEngine._plain(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [TreatmentExportEngine._plain(item) for item in value]
        return value

    @staticmethod
    def _json_bytes(value: Any) -> bytes:
        return (
            json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
        ).encode("utf-8")

    @staticmethod
    def _sha256(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def _write_zip(root: Path, zip_path: Path) -> None:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(item for item in root.rglob("*") if item.is_file()):
                info = zipfile.ZipInfo(
                    path.relative_to(root).as_posix(), date_time=(1980, 1, 1, 0, 0, 0)
                )
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, path.read_bytes())
