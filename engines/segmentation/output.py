"""Parse model output and extract deterministic connected tooth instances."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from domain.case.provenance import DataProvenance
from domain.tooth.segmentation import SegmentationMetadata, ToothInstance, ToothSegmentationResult
from engines.segmentation.preprocessing import PreparedMesh


class SegmentationOutputError(ValueError):
    """Raised when model output cannot be mapped to mesh faces."""


@dataclass(frozen=True)
class ParsedSegmentation:
    """One class label and confidence per input face."""

    labels: np.ndarray
    confidences: np.ndarray


def _as_array(value: object) -> np.ndarray:
    array = np.asarray(value)
    if array.ndim > 0 and array.shape[0] == 1:
        array = array[0]
    return array


def parse_model_outputs(raw_outputs: tuple[object, ...], face_count: int) -> ParsedSegmentation:
    """Parse common ONNX outputs: labels, probabilities/logits, or labels+confidence."""
    if not raw_outputs:
        raise SegmentationOutputError("ONNX model returned no outputs")
    arrays = [_as_array(output) for output in raw_outputs]
    first = arrays[0]

    if first.ndim == 2 and first.shape[0] == face_count:
        labels = np.argmax(first, axis=1).astype(np.int64)
        shifted = first - np.max(first, axis=1, keepdims=True)
        probabilities = np.exp(shifted)
        confidences = (probabilities / probabilities.sum(axis=1, keepdims=True)).max(axis=1)
    elif first.ndim == 1 and first.shape[0] == face_count:
        labels = first.astype(np.int64)
        confidences = (
            _as_array(arrays[1]).astype(np.float32)
            if len(arrays) > 1 and _as_array(arrays[1]).shape == (face_count,)
            else np.ones(face_count, dtype=np.float32)
        )
    else:
        raise SegmentationOutputError(
            f"Expected face labels ({face_count},) or class scores ({face_count}, classes); "
            f"received shape {first.shape}."
        )

    if labels.shape != (face_count,) or confidences.shape != (face_count,):
        raise SegmentationOutputError("Model output lengths do not match input face count")
    if np.any(labels < 0) or not np.all(np.isfinite(confidences)):
        raise SegmentationOutputError("Model output contains invalid labels or confidences")
    if np.any((confidences < 0) | (confidences > 1)):
        raise SegmentationOutputError("Model confidences must be between 0 and 1")
    return ParsedSegmentation(labels=labels, confidences=confidences)


def _face_components(face_indices: np.ndarray, faces: np.ndarray) -> list[np.ndarray]:
    by_vertex: dict[int, list[int]] = {}
    for face_index in face_indices.tolist():
        for vertex in faces[face_index].tolist():
            by_vertex.setdefault(int(vertex), []).append(int(face_index))

    remaining = set(int(index) for index in face_indices.tolist())
    components: list[np.ndarray] = []
    while remaining:
        start = min(remaining)
        stack = [start]
        remaining.remove(start)
        component: list[int] = []
        while stack:
            current = stack.pop()
            component.append(current)
            neighbours = {
                candidate
                for vertex in faces[current].tolist()
                for candidate in by_vertex[int(vertex)]
                if candidate in remaining
            }
            remaining.difference_update(neighbours)
            stack.extend(sorted(neighbours, reverse=True))
        components.append(np.asarray(sorted(component), dtype=np.int64))
    return components


def build_segmentation_result(
    prepared: PreparedMesh,
    parsed: ParsedSegmentation,
    *,
    engine_name: str,
    model_name: str,
    model_version: str,
    provenance: DataProvenance = DataProvenance.EXPERIMENTAL,
) -> ToothSegmentationResult:
    """Convert face labels into connected, geometry-only instances.

    Label zero is treated as background/gingiva. It is never converted into a
    tooth identity; identification is a later pipeline stage.
    """
    components: list[tuple[int, np.ndarray]] = []
    for label in sorted(set(parsed.labels.tolist())):
        if label == 0:
            continue
        label_faces = np.flatnonzero(parsed.labels == label)
        for component in _face_components(label_faces, prepared.faces):
            components.append((int(component.min()), component))
    components.sort(key=lambda item: item[0])

    instances: list[ToothInstance] = []
    for instance_id, (_, triangle_indices) in enumerate(components):
        vertices = np.unique(prepared.faces[triangle_indices].reshape(-1))
        vertex_lookup = {int(vertex): local for local, vertex in enumerate(vertices.tolist())}
        local_faces = tuple(
            tuple(vertex_lookup[int(vertex)] for vertex in prepared.faces[triangle_index].tolist())
            for triangle_index in triangle_indices.tolist()
        )
        mesh_vertices = tuple(
            tuple(float(value) for value in prepared.vertices[vertex].tolist())
            for vertex in vertices.tolist()
        )
        centroid = tuple(
            float(value) for value in prepared.vertices[vertices].mean(axis=0).tolist()
        )
        confidence = float(parsed.confidences[triangle_indices].mean())
        instances.append(
            ToothInstance(
                instance_id=instance_id,
                triangle_indices=tuple(int(index) for index in triangle_indices.tolist()),
                vertex_indices=tuple(int(index) for index in vertices.tolist()),
                mesh_vertices=mesh_vertices,
                mesh_faces=local_faces,
                centroid=centroid,
                confidence=confidence,
                provenance=provenance,
            )
        )

    instance_confidences = [instance.confidence for instance in instances]
    metadata = SegmentationMetadata(
        engine_name=engine_name,
        model_name=model_name,
        model_version=model_version,
        input_triangle_count=len(prepared.faces),
        output_instance_count=len(instances),
        confidence_min=min(instance_confidences, default=0.0),
        confidence_mean=(sum(instance_confidences) / len(instance_confidences))
        if instance_confidences
        else 0.0,
        confidence_max=max(instance_confidences, default=0.0),
        provenance=provenance,
        notes="Geometry-only segmentation; tooth identification has not run.",
    )
    return ToothSegmentationResult(
        instances=tuple(instances), metadata=metadata, source_mesh_path=prepared.source_path
    )
