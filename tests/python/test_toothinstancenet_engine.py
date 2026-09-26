from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import trimesh

from adapters.toothinstancenet.contract import ToothInstanceNetRawOutput
from domain.tooth.identification import ArchType
from engines.segmentation.toothinstancenet import ToothInstanceNetEngine

FIXTURE = Path(__file__).parents[1] / "fixtures" / "synthetic_segmentation_arch.obj"


def raw_output() -> ToothInstanceNetRawOutput:
    mesh = trimesh.load(FIXTURE, force="mesh", process=False)
    vertices = np.asarray(mesh.vertices, dtype=np.float32)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    labels = np.zeros(len(vertices), dtype=np.int64)
    labels[len(vertices) // 2 :] = 1
    labels[len(vertices) // 2] = 2
    return ToothInstanceNetRawOutput(
        instance_labels=labels,
        class_labels=np.array([0, 0, 1], dtype=np.int64),
        class_confidences=np.array([0.8, 0.7, 0.6], dtype=np.float32),
        original_vertices=vertices,
        original_faces=faces,
        transformed_points=vertices,
        sampled_indices=np.arange(len(vertices), dtype=np.int64),
        checkpoint_sha256="a" * 64,
    )


def test_zero_face_fragment_is_excluded_and_duplicates_are_diagnostic() -> None:
    engine = ToothInstanceNetEngine(
        SimpleNamespace(model_name="test", model_version="1"), arch=ArchType.UPPER
    )
    result = engine._map(raw_output(), str(FIXTURE))
    assert result.segmentation.instances
    assert result.diagnostics.duplicate_fdi_numbers == ()
    assert result.diagnostics.missing_fdi_numbers == ()
    assert result.diagnostics.empty_instance_ids == (2,)
    assert result.diagnostics.fdi_authoritative is False
    assert result.diagnostics.clinical_accuracy_claim is False
    assert result.diagnostics.output_class == "ENGINEERING_OUTPUT"
    assert result.status == "identification_incomplete"
    assert all(tooth.identity is None for tooth in result.identification.teeth)
    modes = {tooth.planning_mode for tooth in result.identification.teeth}
    assert modes == {"semantic_only_experimental"}
    assert [tooth.semantic_label for tooth in result.identification.teeth] == [0, 0]
    scores = [tooth.confidence.score for tooth in result.identification.teeth]
    assert scores == pytest.approx([0.8, 0.7])
    assert all(tooth.confidence_available for tooth in result.identification.teeth)


def test_model_unavailable_is_explicit() -> None:
    engine = ToothInstanceNetEngine(
        SimpleNamespace(model_name="test", model_version="1"), arch=ArchType.UPPER
    )
    raw = raw_output()
    raw = raw.__class__(
        instance_labels=np.zeros(len(raw.original_vertices) - 1, dtype=np.int64),
        class_labels=raw.class_labels,
        class_confidences=raw.class_confidences,
        original_vertices=raw.original_vertices,
        original_faces=raw.original_faces,
        transformed_points=raw.transformed_points,
        sampled_indices=raw.sampled_indices,
        checkpoint_sha256=raw.checkpoint_sha256,
    )
    try:
        engine._map(raw, str(FIXTURE))
    except Exception as exc:
        assert "original mesh vertex" in str(exc)
    else:
        raise AssertionError("invalid model output was accepted")
