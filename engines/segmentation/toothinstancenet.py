"""ToothInstanceNet orchestration without changing the existing ONNX engine."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

import numpy as np

from adapters.toothinstancenet.adapter import ToothInstanceNetAdapter
from adapters.toothinstancenet.contract import (
    ToothInstanceNetDiagnostics,
    ToothInstanceNetInferenceError,
    ToothInstanceNetRawOutput,
    ToothInstanceNetUnavailableError,
)
from adapters.toothinstancenet.preprocessing import prepare_mesh
from domain.case.provenance import DataProvenance
from domain.tooth.identification import (
    ArchType,
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
    timings_ms: dict | None = None


class ToothInstanceNetEngine:
    """Run only the official learned-region instance pipeline."""

    def __init__(self, adapter: ToothInstanceNetAdapter, *, arch: ArchType) -> None:
        self.adapter = adapter
        self.arch = arch

    def segment(self, mesh_file_path: str) -> ToothInstanceNetInferenceResult:
        try:
            started = perf_counter()
            prepared = prepare_mesh(mesh_file_path, self.adapter.config)
            preprocessed = perf_counter()
            raw = self.adapter.infer(prepared, lower=self.arch is ArchType.LOWER)
            inferred = perf_counter()
            mapped = self._map(raw, mesh_file_path)
            finished = perf_counter()
        except ToothInstanceNetUnavailableError:
            raise
        except Exception as exc:  # noqa: BLE001 - runtime boundary
            raise ToothInstanceNetInferenceError(
                f"ToothInstanceNet inference failed: {exc}"
            ) from exc
        peak_gpu = self.adapter.runtime_metadata.get("peak_gpu_memory_bytes")
        timings = {
            "preprocess_ms": (preprocessed - started) * 1000,
            "inference_ms": (inferred - preprocessed) * 1000,
            "postprocess_ms": (finished - inferred) * 1000,
            "total_ms": (finished - started) * 1000,
            "peak_gpu_memory_bytes": peak_gpu,
        }
        return ToothInstanceNetInferenceResult(
            mapped.segmentation,
            mapped.identification,
            mapped.diagnostics,
            mapped.status,
            timings,
        )

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
        model_classes: list[tuple[int, int | None]] = []
        confidences: list[float | None] = []
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
            model_class = (
                int(class_labels[instance_id])
                if 0 <= instance_id < len(class_labels)
                else None
            )
            if model_class is not None and not 0 <= model_class < 7:
                model_class = None
            confidence_value = None
            if 0 <= instance_id < len(class_confidences):
                candidate = float(class_confidences[instance_id])
                if np.isfinite(candidate) and 0.0 <= candidate <= 1.0:
                    confidence_value = candidate
            model_classes.append((len(instances), model_class))
            confidences.append(confidence_value)
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
                    confidence=confidence_value if confidence_value is not None else 0.0,
                    provenance=DataProvenance.EXPERIMENTAL,
                    notes=(
                        "ToothInstanceNet engineering output. "
                        "Seven-class label is semantic, not authoritative FDI. "
                        + (
                            "Per-instance model confidence is stored."
                            if confidence_value is not None
                            else "No per-instance model confidence was provided."
                        )
                    ),
                    semantic_label=model_class,
                    arch=self.arch.value,
                )
            )

        available = [value for value in confidences if value is not None]
        segmentation = ToothSegmentationResult(
            instances=tuple(instances),
            metadata=SegmentationMetadata(
                engine_name="toothinstancenet-segmentation",
                model_name=self.adapter.model_name,
                model_version=self.adapter.model_version,
                input_triangle_count=len(raw.original_faces),
                output_instance_count=len(instances),
                confidence_min=min(available) if available else 0.0,
                confidence_mean=float(np.mean(available)) if available else 0.0,
                confidence_max=max(available) if available else 0.0,
                provenance=DataProvenance.EXPERIMENTAL,
                notes=(
                    "ENGINEERING_OUTPUT. Seven-class labels are semantic classes, "
                    "not authoritative FDI. clinical_accuracy_claim=false. "
                    "Confidence statistics use only per-instance model scores."
                ),
            ),
            source_mesh_path=source_path,
        )
        if not available:
            segmentation = ToothSegmentationResult(
                instances=segmentation.instances,
                metadata=SegmentationMetadata(
                    engine_name=segmentation.metadata.engine_name,
                    model_name=segmentation.metadata.model_name,
                    model_version=segmentation.metadata.model_version,
                    input_triangle_count=segmentation.metadata.input_triangle_count,
                    output_instance_count=segmentation.metadata.output_instance_count,
                    confidence_min=0.0,
                    confidence_mean=0.0,
                    confidence_max=0.0,
                    provenance=segmentation.metadata.provenance,
                    notes=(
                        segmentation.metadata.notes
                        + " No per-instance confidence was provided; "
                        "0.0 is not a model score."
                    ),
                ),
                source_mesh_path=source_path,
            )
        status = "identification_incomplete"
        diagnostics = ToothInstanceNetDiagnostics(
            state=status,
            fdi_by_instance=tuple((item.instance_id, None) for item in instances),
            duplicate_fdi_numbers=(),
            missing_fdi_numbers=(),
            empty_instance_ids=tuple(empty_ids),
            notes=(
                "Raw model classes are semantic labels. They are not FDI, "
                "do not distinguish left from right, and are not a clinical numbering.",
                "clinical_accuracy_claim=false.",
            ),
            model_class_by_instance=tuple(model_classes),
            label_semantics="seven_class_semantic_not_unique_fdi",
            fdi_authoritative=False,
            output_class="ENGINEERING_OUTPUT",
            clinical_accuracy_claim=False,
        )
        identified = []
        stamped_instances = []
        for instance, confidence_value in zip(instances, confidences, strict=True):
            arch_value = self.arch.value
            tooth_ref = f"{arch_value}:instance:{instance.instance_id}"
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
                arch=arch_value,
            )
            stamped_instances.append(stamped)
            identified.append(
                IdentifiedTooth(
                    instance=stamped,
                    identity=None,
                    landmarks=None,
                    coordinate_system=None,
                    confidence=IdentificationConfidence(
                        confidence_value if confidence_value is not None else 0.0,
                        IdentificationStatus.UNCERTAIN,
                        (
                            "Semantic class only. FDI was not assigned.",
                            "Confidence is the model softmax for this instance."
                            if confidence_value is not None
                            else "The model did not provide a per-instance confidence.",
                        ),
                    ),
                    provenance=DataProvenance.EXPERIMENTAL,
                    fixture=False,
                    notes="Engineering segmentation output. Not a clinical identity.",
                    tooth_ref=tooth_ref,
                    semantic_label=instance.semantic_label,
                    planning_mode="semantic_only_experimental",
                    confidence_available=confidence_value is not None,
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
                "ToothInstanceNet engineering output. Semantic classes are not FDI. "
                "clinical_accuracy_claim=false."
            ),
        )
        return ToothInstanceNetInferenceResult(segmentation, identification, diagnostics, status)
