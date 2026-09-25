"""FV-01 — provenance / no fabricated FDI / no synthetic geometry in clinical calculations."""

from __future__ import annotations

from pathlib import Path

import pytest

from adapters.toothinstancenet.fixture import load_validated_fixture
from domain.tooth.identification import ArchType
from domain.tooth.occlusion import OcclusionAvailability, unavailable_occlusion


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ZIP = ROOT / "official_real_case_stage2_verified_v1.zip"
ARTIFACT_DIR = ROOT / ".research" / "tmp" / "official_real_case_stage2_verified_v1"


def _artifact_path() -> Path:
    if ARTIFACT_DIR.is_dir():
        return ARTIFACT_DIR
    return ARTIFACT_ZIP


@pytest.mark.skipif(
    not ARTIFACT_ZIP.is_file() and not ARTIFACT_DIR.is_dir(),
    reason="Official real-case artifact not present",
)
def test_real_case_fixture_does_not_assign_clinical_fdi() -> None:
    path = _artifact_path()
    upper = load_validated_fixture(path, arch=ArchType.UPPER)
    lower = load_validated_fixture(path, arch=ArchType.LOWER)
    for arch_result in (upper, lower):
        assert arch_result.identification.teeth
        for tooth in arch_result.identification.teeth:
            assert tooth.identity is None
            assert tooth.landmarks is None
        for _instance_id, fdi in arch_result.diagnostics.fdi_by_instance:
            assert fdi is None


def test_occlusion_is_explicitly_unavailable_not_fabricated() -> None:
    occlusion = unavailable_occlusion()
    assert occlusion.availability is OcclusionAvailability.UNAVAILABLE
    assert occlusion.contact_count is None
    assert occlusion.occlusal_contacts is OcclusionAvailability.UNAVAILABLE
    payload = occlusion.payload()
    assert payload["contact_count"] is None
    assert payload["availability"] == "unavailable"


def test_synthetic_gingiva_module_is_presentation_only() -> None:
    """Guard: synthetic gingiva documents presentation-only — not clinical evidence."""
    gingiva_path = ROOT / "apps" / "web" / "src" / "viewer" / "syntheticGingiva.ts"
    text = gingiva_path.read_text()
    assert "PRESENTATION ONLY" in text
    assert "must never feed treatment math" in text
    assert "presentationOnly" in text
