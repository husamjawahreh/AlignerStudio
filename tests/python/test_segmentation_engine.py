from pathlib import Path

import numpy as np
import pytest

from adapters.meshsegnet.onnx_adapter import (
    OnnxRuntimeSegmentationAdapter,
    SegmentationModelUnavailableError,
)
from domain.case.provenance import DataProvenance
from domain.tooth.segmentation import (
    SegmentationMetadata,
    ToothInstance,
    ToothSegmentationResult,
)
from engines.segmentation.onnx_engine import OnnxSegmentationEngine
from engines.segmentation.output import SegmentationOutputError, parse_model_outputs
from engines.segmentation.preprocessing import (
    MeshPreprocessingConfig,
    MeshPreprocessingError,
    prepare_mesh,
)

FIXTURE = Path(__file__).parents[1] / "fixtures" / "synthetic_segmentation_arch.obj"


class FakeSegmentationAdapter:
    model_name = "synthetic-test-model"
    model_version = "test-1"

    def infer(self, prepared_mesh):
        assert prepared_mesh.face_features.shape == (8, 15)
        labels = np.array([1, 1, 1, 1, 2, 2, 2, 2], dtype=np.int64)
        confidence = np.array([0.9, 0.9, 0.8, 0.8, 0.7, 0.7, 0.6, 0.6])
        return (labels, confidence)


def test_mesh_preprocessing_normalizes_and_builds_features() -> None:
    prepared = prepare_mesh(FIXTURE, MeshPreprocessingConfig(minimum_triangle_count=1))
    assert prepared.faces.shape == (8, 3)
    assert prepared.face_features.shape == (8, 15)
    assert np.allclose(prepared.normalized_vertices.mean(axis=0), 0.0)
    assert np.max(np.linalg.norm(prepared.normalized_vertices, axis=1)) == pytest.approx(1.0)


def test_invalid_mesh_input_fails_explicitly(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.obj"
    invalid.write_text("not a mesh")
    with pytest.raises(MeshPreprocessingError):
        prepare_mesh(invalid, MeshPreprocessingConfig(minimum_triangle_count=1))


def test_output_parser_accepts_labels_and_confidences() -> None:
    parsed = parse_model_outputs((np.array([1, 0, 2]), np.array([0.8, 0.4, 0.9])), face_count=3)
    assert parsed.labels.tolist() == [1, 0, 2]
    assert parsed.confidences.tolist() == pytest.approx([0.8, 0.4, 0.9])


def test_output_parser_accepts_class_scores() -> None:
    scores = np.array([[0.1, 0.9], [0.8, 0.2]])
    parsed = parse_model_outputs((scores,), face_count=2)
    assert parsed.labels.tolist() == [1, 0]
    assert parsed.confidences.tolist() == pytest.approx([0.6899744811, 0.6456563062], abs=1e-6)


def test_output_parser_rejects_wrong_face_count() -> None:
    with pytest.raises(SegmentationOutputError):
        parse_model_outputs((np.array([1, 2]),), face_count=3)


def test_engine_extracts_deterministically_ordered_geometry_only_instances() -> None:
    result = OnnxSegmentationEngine(
        adapter=FakeSegmentationAdapter(),
        preprocessing=MeshPreprocessingConfig(minimum_triangle_count=1),
    ).segment(str(FIXTURE))

    assert isinstance(result, ToothSegmentationResult)
    assert [instance.instance_id for instance in result.instances] == [0, 1]
    assert [len(instance.mesh_faces) for instance in result.instances] == [4, 4]
    assert [instance.triangle_indices[0] for instance in result.instances] == [0, 4]
    assert all(instance.provenance == DataProvenance.EXPERIMENTAL for instance in result.instances)
    assert result.metadata.provenance == DataProvenance.EXPERIMENTAL
    assert result.metadata.fixture is False
    assert all(not hasattr(instance, "fdi_number") for instance in result.instances)


def test_missing_model_fails_without_fallback() -> None:
    adapter = OnnxRuntimeSegmentationAdapter("/does/not/exist/model.onnx")
    with pytest.raises(SegmentationModelUnavailableError, match="unavailable"):
        adapter.infer(prepare_mesh(FIXTURE, MeshPreprocessingConfig(minimum_triangle_count=1)))


def test_adapter_contract_can_be_injected_without_onnxruntime() -> None:
    result = OnnxSegmentationEngine(
        adapter=FakeSegmentationAdapter(),
        preprocessing=MeshPreprocessingConfig(minimum_triangle_count=1),
    ).segment(str(FIXTURE))
    assert result.metadata.model_name == "synthetic-test-model"
    assert result.metadata.model_version == "test-1"


def test_segmentation_result_rejects_non_contiguous_instance_ids() -> None:
    instance = ToothInstance(
        instance_id=1,
        triangle_indices=(0,),
        vertex_indices=(0, 1, 2),
        mesh_vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        mesh_faces=((0, 1, 2),),
        centroid=(0.0, 0.0, 0.0),
        confidence=0.5,
        provenance=DataProvenance.EXPERIMENTAL,
    )
    metadata = SegmentationMetadata(
        engine_name="test",
        model_name="test",
        model_version="1",
        input_triangle_count=1,
        output_instance_count=1,
        confidence_min=0.5,
        confidence_mean=0.5,
        confidence_max=0.5,
        provenance=DataProvenance.EXPERIMENTAL,
    )
    with pytest.raises(ValueError, match="contiguous"):
        ToothSegmentationResult((instance,), metadata, "fixture.obj")
