"""P3 anatomical intelligence — serialize existing evidence without invention."""

from __future__ import annotations

import pytest

from domain.case.provenance import DataProvenance
from domain.tooth.anatomy_extent import AnatomyExtent, default_anatomy_extent_for_stl
from domain.tooth.identification import ArchType
from domain.tooth.occlusion import OcclusionAvailability, unavailable_occlusion
from engines.arrangement.anatomical_intelligence import (
    build_anatomical_intelligence_summary,
    serialize_arch_measurements,
    serialize_identified_tooth,
)
from engines.arrangement.arch_analysis import ArchAnalysisEngine
from engines.arrangement.identification import ToothIdentificationEngine
from engines.validation.root_bone import (
    RootBonePathwayError,
    assert_root_bone_pathway_allowed,
    root_bone_pathway_supported,
)
from tests.fixtures.synthetic_arch import build_synthetic_arch


def test_complete_arch_serializes_landmarks_axes_and_fdi() -> None:
    identification = ToothIdentificationEngine().identify(
        build_synthetic_arch(ArchType.UPPER), ArchType.UPPER
    )
    tooth = identification.identified[0]
    payload = serialize_identified_tooth(tooth)

    assert tooth.identity is not None
    assert payload["fdi_number"] == tooth.identity.number
    assert payload["landmarks"] is not None
    assert payload["coordinate_system"] is not None
    assert payload["movement_reference_frame"] == payload["coordinate_system"]
    assert payload["anatomy_extent"] == AnatomyExtent.CROWN_ONLY_STL.value
    assert payload["provenance"] == tooth.provenance.value


def test_arch_measurements_include_orientation_and_midline() -> None:
    identification = ToothIdentificationEngine().identify(
        build_synthetic_arch(ArchType.UPPER), ArchType.UPPER
    )
    measurements = ArchAnalysisEngine().analyze(identification)
    payload = serialize_arch_measurements(measurements)

    assert payload is not None
    assert payload["orientation_lateral_axis"] is not None
    assert payload["orientation_anterior_axis"] is not None
    assert payload["orientation_vertical_axis"] is not None
    assert payload["geometric_midline_point"] is not None
    assert len(payload["consecutive_tooth_distances"]) == len(measurements.ordered_instance_ids) - 1


def test_anatomical_summary_marks_occlusion_unavailable_for_crown_stl() -> None:
    identification = ToothIdentificationEngine().identify(
        build_synthetic_arch(ArchType.LOWER), ArchType.LOWER
    )
    measurements = ArchAnalysisEngine().analyze(identification)
    summary = build_anatomical_intelligence_summary(
        identification=identification,
        arch_measurements=measurements,
    )
    payload = summary.payload()

    assert payload["landmarks_available"] is True
    assert payload["local_axes_available"] is True
    assert payload["arch_orientation_available"] is True
    assert payload["arch_form_available"] is True
    assert payload["midline_available"] is True
    assert payload["occlusion"]["availability"] == OcclusionAvailability.UNAVAILABLE.value
    assert payload["occlusion"]["occlusal_contacts"] == OcclusionAvailability.UNAVAILABLE.value
    assert payload["data_quality"]["scale_validation"] == "unverified"
    assert payload["data_quality"]["units"] == "unverified"
    assert payload["data_quality"]["missing_anatomy"] is True
    assert payload["data_quality"]["incomplete_occlusion"] is True
    assert payload["anatomy_extent"] == AnatomyExtent.CROWN_ONLY_STL.value


def test_unavailable_occlusion_never_invents_contacts() -> None:
    occlusion = unavailable_occlusion(provenance=DataProvenance.EXPERIMENTAL)
    assert occlusion.contact_count is None
    assert occlusion.bite_record is OcclusionAvailability.UNAVAILABLE


def test_root_bone_pathway_blocked_for_crown_only_stl() -> None:
    extent = default_anatomy_extent_for_stl()
    assert root_bone_pathway_supported(extent) is False
    with pytest.raises(RootBonePathwayError):
        assert_root_bone_pathway_allowed(extent)


def test_root_bone_pathway_allowed_only_for_cbct_extent() -> None:
    assert root_bone_pathway_supported(AnatomyExtent.ROOT_BONE_CBCT) is True
    assert_root_bone_pathway_allowed(AnatomyExtent.ROOT_BONE_CBCT)
