"""Explicit test-only loader for validated ToothInstanceNet artifact JSON."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from adapters.toothinstancenet.contract import ToothInstanceNetDiagnostics
from domain.case.provenance import DataProvenance
from domain.tooth.identification import (
    ArchType,
    FDIToothIdentity,
    IdentificationConfidence,
    IdentificationStatus,
    IdentifiedTooth,
    ToothIdentificationResult,
)
from domain.tooth.segmentation import (
    SegmentationMetadata,
    ToothInstance,
    ToothSegmentationResult,
)
from engines.segmentation.toothinstancenet import ToothInstanceNetInferenceResult


class ToothInstanceNetFixtureError(ValueError):
    """Raised when an explicit validated artifact is malformed."""


def load_validated_fixture(
    path: str | Path,
    *,
    arch: ArchType,
    source_mesh_path: str | Path | None = None,
) -> ToothInstanceNetInferenceResult:
    """Load only an explicitly selected validated artifact; never auto-fallback."""
    artifact_path = Path(path)
    if not artifact_path.is_file():
        raise ToothInstanceNetFixtureError(f"Validated fixture is unavailable: {artifact_path}")
    payload = json.loads(artifact_path.read_text())
    if payload.get("source_kind") != "validated_real_case":
        raise ToothInstanceNetFixtureError("Fixture source_kind must be validated_real_case")
    if payload.get("fixture") is not True or payload.get("experimental") is not True:
        raise ToothInstanceNetFixtureError(
            "Validated fixture must be explicitly fixture and experimental"
        )
    if payload.get("arch") != arch.value:
        raise ToothInstanceNetFixtureError("Fixture arch does not match the requested arch")
    recorded_hash = payload.get("source_stl_sha256")
    if source_mesh_path is not None and recorded_hash:
        digest = hashlib.sha256(Path(source_mesh_path).read_bytes()).hexdigest()
        if digest != recorded_hash:
            raise ToothInstanceNetFixtureError(
                "Uploaded STL hash does not match validated fixture source: "
                f"{digest} != {recorded_hash}"
            )

    instances: list[ToothInstance] = []
    identified: list[IdentifiedTooth] = []
    fdi_by_instance: list[tuple[int, int | None]] = []
    seen_fdi: set[int] = set()
    duplicate_fdi: set[int] = set()
    for raw in payload.get("instances", []):
        vertices = tuple(tuple(float(value) for value in point) for point in raw["vertices"])
        faces = tuple(tuple(int(value) for value in face) for face in raw["faces"])
        instance = ToothInstance(
            instance_id=len(instances),
            triangle_indices=tuple(int(value) for value in raw.get("triangle_indices", [])),
            vertex_indices=tuple(
                int(value) for value in raw.get("vertex_indices", range(len(vertices)))
            ),
            mesh_vertices=vertices,
            mesh_faces=faces,
            centroid=tuple(float(value) for value in raw["centroid"]),
            confidence=float(raw["confidence"]),
            provenance=DataProvenance.EXPERIMENTAL,
            fixture=True,
            notes="Explicit validated ToothInstanceNet artifact; not production inference.",
        )
        fdi = raw.get("fdi_number")
        if fdi is not None:
            fdi = int(fdi)
            if fdi in seen_fdi:
                duplicate_fdi.add(fdi)
            seen_fdi.add(fdi)
        fdi_by_instance.append((instance.instance_id, fdi))
        identity = None
        if fdi is not None:
            quadrant = fdi // 10
            identity = FDIToothIdentity(fdi, arch, quadrant, fdi % 10)
        identified.append(
            IdentifiedTooth(
                instance=instance,
                identity=identity,
                landmarks=None,
                coordinate_system=None,
                confidence=IdentificationConfidence(
                    instance.confidence,
                    IdentificationStatus.IDENTIFIED if identity else IdentificationStatus.UNCERTAIN,
                    ("Validated artifact identity preserved without repair.",),
                ),
                provenance=DataProvenance.EXPERIMENTAL,
                fixture=True,
                notes="Validated real-case artifact fixture; not automatically selected.",
            )
        )
        instances.append(instance)

    segmentation = ToothSegmentationResult(
        instances=tuple(instances),
        metadata=SegmentationMetadata(
            engine_name="toothinstancenet-validated-fixture",
            model_name="toothinstancenet",
            model_version=str(payload.get("model_version", "validated-artifact")),
            input_triangle_count=int(payload.get("input_faces", 0)),
            output_instance_count=len(instances),
            confidence_min=min((item.confidence for item in instances), default=0.0),
            confidence_mean=sum(item.confidence for item in instances) / len(instances)
            if instances
            else 0.0,
            confidence_max=max((item.confidence for item in instances), default=0.0),
            provenance=DataProvenance.EXPERIMENTAL,
            fixture=True,
            notes="Explicit validated_real_case artifact; fixture path is never automatic.",
        ),
        source_mesh_path=str(payload.get("source_mesh_path", "validated_real_case")),
    )
    fdis = {fdi for _, fdi in fdi_by_instance if fdi is not None}
    expected = set(range(31, 38) if arch is ArchType.LOWER else range(11, 18))
    missing = tuple(sorted(expected - fdis))
    diagnostics = ToothInstanceNetDiagnostics(
        state="identification_incomplete" if duplicate_fdi or missing else "planning_ready",
        fdi_by_instance=tuple(fdi_by_instance),
        duplicate_fdi_numbers=tuple(sorted(duplicate_fdi)),
        missing_fdi_numbers=missing,
        empty_instance_ids=tuple(int(value) for value in payload.get("empty_instance_ids", [])),
        notes=("source_kind=validated_real_case; fixture=true; experimental=true",),
    )
    return ToothInstanceNetInferenceResult(
        segmentation=segmentation,
        identification=ToothIdentificationResult(
            arch=arch,
            teeth=tuple(identified),
            provenance=DataProvenance.EXPERIMENTAL,
            fixture=True,
            notes="Validated artifact identity preserved; fixture is explicit and test-only.",
        ),
        diagnostics=diagnostics,
        status=diagnostics.state,
    )
