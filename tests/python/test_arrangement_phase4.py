from dataclasses import replace

import pytest

from domain.case.provenance import DataProvenance
from domain.tooth.identification import ArchType, IdentificationStatus
from engines.arrangement.arch_analysis import ArchAnalysisEngine
from engines.arrangement.identification import ToothIdentificationEngine
from tests.fixtures.synthetic_arch import build_synthetic_arch


def test_upper_identification_is_deterministic_and_fdi_ordered() -> None:
    segmentation = build_synthetic_arch(ArchType.UPPER)
    engine = ToothIdentificationEngine()
    first = engine.identify(segmentation, ArchType.UPPER)
    second = engine.identify(segmentation, ArchType.UPPER)

    assert first == second
    assert len(first.identified) == 16
    assert [tooth.identity.number for tooth in first.identified] == [
        18,
        17,
        16,
        15,
        14,
        13,
        12,
        11,
        21,
        22,
        23,
        24,
        25,
        26,
        27,
        28,
    ]
    assert first.provenance == DataProvenance.FIXTURE
    assert first.fixture is True


def test_lower_arch_uses_lower_fdi_quadrants() -> None:
    result = ToothIdentificationEngine().identify(
        build_synthetic_arch(ArchType.LOWER), ArchType.LOWER
    )
    assert [tooth.identity.number for tooth in result.identified] == [
        48,
        47,
        46,
        45,
        44,
        43,
        42,
        41,
        31,
        32,
        33,
        34,
        35,
        36,
        37,
        38,
    ]


def test_incomplete_arch_remains_uncertain_without_fdi_guessing() -> None:
    segmentation = build_synthetic_arch(ArchType.UPPER)
    incomplete = replace(
        segmentation,
        instances=segmentation.instances[:-1],
        metadata=replace(segmentation.metadata, output_instance_count=15),
    )
    result = ToothIdentificationEngine().identify(incomplete, ArchType.UPPER)
    assert len(result.identified) == 0
    assert len(result.uncertain) == 15
    assert all(tooth.identity is None for tooth in result.teeth)


def test_malformed_geometry_is_unidentified() -> None:
    segmentation = build_synthetic_arch(ArchType.UPPER)
    malformed = replace(segmentation.instances[0], mesh_vertices=(), mesh_faces=())
    updated = replace(segmentation, instances=(malformed, *segmentation.instances[1:]))
    result = ToothIdentificationEngine().identify(updated, ArchType.UPPER)
    by_id = {tooth.instance.instance_id: tooth for tooth in result.teeth}
    assert by_id[0].confidence.status is IdentificationStatus.UNIDENTIFIED
    assert by_id[0].identity is None


def test_coordinate_frames_are_stable_and_orthogonal() -> None:
    result = ToothIdentificationEngine().identify(
        build_synthetic_arch(ArchType.UPPER), ArchType.UPPER
    )
    frame = result.identified[0].coordinate_system
    assert frame is not None
    axes = [frame.lateral_axis, frame.anterior_axis, frame.vertical_axis]
    for axis in axes:
        assert sum(value * value for value in axis) == pytest.approx(1.0)
    for first in axes:
        for second in axes:
            if first is not second:
                assert sum(a * b for a, b in zip(first, second, strict=True)) == pytest.approx(0.0)


def test_arch_analysis_orders_teeth_and_measures_descriptive_geometry() -> None:
    identification = ToothIdentificationEngine().identify(
        build_synthetic_arch(ArchType.UPPER), ArchType.UPPER
    )
    measurements = ArchAnalysisEngine().analyze(identification)
    assert measurements.ordered_instance_ids == tuple(range(16))
    assert measurements.total_width == pytest.approx(15.0)
    assert measurements.left_half_width == pytest.approx(7.5)
    assert measurements.right_half_width == pytest.approx(7.5)
    assert measurements.anterior_width == pytest.approx(1.0)
    assert measurements.posterior_width == pytest.approx(15.0)
    assert len(measurements.consecutive_tooth_distances) == 15
    assert measurements.provenance == DataProvenance.FIXTURE
    assert "descriptive" in measurements.notes.lower()


def test_arch_analysis_rejects_no_identified_geometry() -> None:
    segmentation = build_synthetic_arch(ArchType.UPPER)
    incomplete = replace(
        segmentation,
        instances=segmentation.instances[:-1],
        metadata=replace(segmentation.metadata, output_instance_count=15),
    )
    identification = ToothIdentificationEngine().identify(incomplete, ArchType.UPPER)
    with pytest.raises(ValueError, match="identified teeth"):
        ArchAnalysisEngine().analyze(identification)
