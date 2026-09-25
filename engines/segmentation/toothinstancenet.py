"""ToothInstanceNet orchestration without changing the existing ONNX engine."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from adapters.toothinstancenet.adapter import ToothInstanceNetAdapter
from adapters.toothinstancenet.contract import (
    ToothInstanceNetDiagnostics,
    ToothInstanceNetInferenceError,
    ToothInstanceNetRawOutput,
    ToothInstanceNetUnavailableError,
    verified_fdi_number,
)
from adapters.toothinstancenet.preprocessing import prepare_mesh
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


@dataclass(frozen=True)
class ToothInstanceNetInferenceResult:
    """Existing geometry segmentation plus model identity diagnostics."""

    segmentation: ToothSegmentationResult
    identification: ToothIdentificationResult
    diagnostics: ToothInstanceNetDiagnostics
    status: str


class ToothInstanceNetEngine:
    """Run only the official learned-region instance pipeline."""

    def __init__(self, adapter: ToothInstanceNetAdapter, *, arch: ArchType) -> None:
        self.adapter = adapter
        self.arch = arch

    def segment(self, mesh_file_path: str) -> ToothInstanceNetInferenceResult:
        try:
            prepared = prepare_mesh(mesh_file_path, self.adapter.config)
            raw = self.adapter.infer(prepared, lower=self.arch is ArchType.LOWER)
            return self._map(raw, mesh_file_path)
        except ToothInstanceNetUnavailableError:
            raise
        except Exception as exc:  # noqa: BLE001 - runtime boundary
            raise ToothInstanceNetInferenceError(
                f"ToothInstanceNet inference failed: {exc}"
            ) from exc

    def _map(
        self, raw: ToothInstanceNetRawOutput, source_path: str
    ) -> ToothInstanceNetInferenceResult:
        instance_labels = np.asarray(raw.instance_labels, dtype=np.int64)
        class_labels = np.asarray(raw.class_labels, dtype=np.int64)
        class_confidences = np.asarray(raw.class_confidences, dtype=np.float32)
        if instance_labels.shape != (len(raw.original_vertices),):
            raise ToothInstanceNetUnavailableError(
                "ToothInstanceNet did not return one instance label per original mesh vertex."
            )
        if len(class_labels) != len(class_confidences):
            raise ToothInstanceNetUnavailableError(
                "ToothInstanceNet class outputs have inconsistent lengths."
            )

        instances: list[ToothInstance] = []
        fdi_by_instance: list[tuple[int, int | None]] = []
        duplicate_fdi: list[int] = []
        seen_fdi: set[int] = set()
        empty_ids: list[int] = []
        for instance_id in sorted(int(value) for value in np.unique(instance_labels) if value >= 0):
            vertex_indices = np.flatnonzero(instance_labels == instance_id)
            if len(vertex_indices) == 0:
                empty_ids.append(instance_id)
                continue
            face_mask = np.all(np.isin(raw.original_faces, vertex_indices), axis=1)
            triangle_indices = np.flatnonzero(face_mask)
            if len(triangle_indices) == 0:
                empty_ids.append(instance_id)
                continue
            local_vertices = np.unique(raw.original_faces[triangle_indices].reshape(-1))
            lookup = {int(index): local for local, index in enumerate(local_vertices.tolist())}
            local_faces = tuple(
                tuple(lookup[int(index)] for index in raw.original_faces[triangle].tolist())
                for triangle in triangle_indices.tolist()
            )
            confidence = float(np.mean(class_confidences)) if len(class_confidences) else 0.0
            instances.append(
                ToothInstance(
                    instance_id=len(instances),
                    triangle_indices=tuple(int(index) for index in triangle_indices.tolist()),
                    vertex_indices=tuple(int(index) for index in local_vertices.tolist()),
                    mesh_vertices=tuple(
                        tuple(float(value) for value in raw.original_vertices[index].tolist())
                        for index in local_vertices.tolist()
                    ),
                    mesh_faces=local_faces,
                    centroid=tuple(
                        float(value)
                        for value in raw.original_vertices[vertex_indices].mean(axis=0).tolist()
                    ),
                    confidence=confidence,
                    provenance=DataProvenance.EXPERIMENTAL,
                    notes=(
                        "ToothInstanceNet model output; zero-face fragments excluded "
                        "at domain boundary."
                    ),
                )
            )
            model_class = (
                int(class_labels[min(instance_id, len(class_labels) - 1)])
                if len(class_labels)
                else -1
            )
            fdi = verified_fdi_number(model_class, lower=self.arch is ArchType.LOWER)
            fdi_by_instance.append((len(instances) - 1, fdi))
            if fdi is not None and fdi in seen_fdi:
                duplicate_fdi.append(fdi)
            if fdi is not None:
                seen_fdi.add(fdi)

        segmentation = ToothSegmentationResult(
            instances=tuple(instances),
            metadata=SegmentationMetadata(
                engine_name="toothinstancenet-segmentation",
                model_name=self.adapter.model_name,
                model_version=self.adapter.model_version,
                input_triangle_count=len(raw.original_faces),
                output_instance_count=len(instances),
                confidence_min=min((item.confidence for item in instances), default=0.0),
                confidence_mean=float(np.mean([item.confidence for item in instances]))
                if instances
                else 0.0,
                confidence_max=max((item.confidence for item in instances), default=0.0),
                provenance=DataProvenance.EXPERIMENTAL,
                notes="Model FDI is retained separately from geometry segmentation.",
            ),
            source_mesh_path=source_path,
        )
        expected = set(range(31, 38) if self.arch is ArchType.LOWER else range(11, 18))
        found = {fdi for _, fdi in fdi_by_instance if fdi is not None}
        missing = tuple(sorted(expected - found))
        status = (
            "planning_ready" if not duplicate_fdi and not missing else "identification_incomplete"
        )
        diagnostics = ToothInstanceNetDiagnostics(
            state=status,
            fdi_by_instance=tuple(fdi_by_instance),
            duplicate_fdi_numbers=tuple(sorted(set(duplicate_fdi))),
            missing_fdi_numbers=missing,
            empty_instance_ids=tuple(empty_ids),
            notes=(
                "FDI is model output mapped through the official seven-class mapping; "
                "no repair was applied.",
            ),
        )
        identified = []
        stamped_instances = []
        for instance, (_, fdi) in zip(segmentation.instances, fdi_by_instance, strict=False):
            identity = None
            if fdi is not None:
                quadrant = 4 if self.arch is ArchType.LOWER else 1
                identity = FDIToothIdentity(fdi, self.arch, quadrant, fdi % 10)
            # Stable instance identity for planning — never invent clinical FDI here.
            arch_value = self.arch.value
            tooth_ref = instance.tooth_ref or f"{arch_value}:instance:{instance.instance_id}"
            stamped = ToothInstance(
                instance_id=instance.instance_id,
                triangle_indices=instance.triangle_indices,
                vertex_indices=instance.vertex_indices,
                mesh_vertices=instance.mesh_vertices,
                mesh_faces=instance.mesh_faces,
                centroid=instance.centroid,
                confidence=instance.confidence,
                provenance=instance.provenance,
                fixture=instance.fixture,
                notes=instance.notes,
                tooth_ref=tooth_ref,
                semantic_label=instance.semantic_label,
                arch=instance.arch or arch_value,
            )
            stamped_instances.append(stamped)
            identified.append(
                IdentifiedTooth(
                    instance=stamped,
                    identity=identity,
                    landmarks=None,
                    coordinate_system=None,
                    confidence=IdentificationConfidence(
                        instance.confidence,
                        IdentificationStatus.IDENTIFIED
                        if identity
                        else IdentificationStatus.UNCERTAIN,
                        ("ToothInstanceNet identity retained without duplicate/missing repair.",),
                    ),
                    provenance=DataProvenance.EXPERIMENTAL,
                    fixture=False,
                    notes="Model identity is separate from geometric identification.",
                    tooth_ref=tooth_ref,
                    semantic_label=instance.semantic_label,
                    planning_mode="clinical_fdi" if identity else "semantic_only_experimental",
                )
            )
        segmentation = ToothSegmentationResult(
            instances=tuple(stamped_instances),
            metadata=segmentation.metadata,
            source_mesh_path=segmentation.source_mesh_path,
        )
        identification = ToothIdentificationResult(
            arch=self.arch,
            teeth=tuple(identified),
            provenance=DataProvenance.EXPERIMENTAL,
            fixture=False,
            notes=(
                "ToothInstanceNet model FDI view; geometric identification engine "
                "remains unchanged."
            ),
        )
        return ToothInstanceNetInferenceResult(segmentation, identification, diagnostics, status)
