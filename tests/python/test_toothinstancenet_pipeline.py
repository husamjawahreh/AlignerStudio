from pathlib import Path

from app.pipeline_diagnostics import process_uploaded_case

from domain.tooth.identification import ArchType
from tests.python.test_toothinstancenet_fixture import _write_artifact


def test_validated_fixture_requires_explicit_backend_selection(tmp_path, monkeypatch) -> None:
    fixture = _write_artifact(tmp_path / "validated")
    monkeypatch.setenv("ALIGNERSTUDIO_TOOTHINSTANCENET_VALIDATED_FIXTURE_DIR", str(fixture))
    monkeypatch.delenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", raising=False)
    monkeypatch.delenv("ALIGNERSTUDIO_ALLOW_TEST_FIXTURE_BACKEND", raising=False)

    # Without the fixture backend, a missing upload fails closed on the real path —
    # never silently loading the validated fixture.
    diagnostic = process_uploaded_case(str(tmp_path / "missing-upload.stl"), ArchType.UPPER)

    assert diagnostic.state.value in {"model_unavailable", "segmentation_failed"}
    assert diagnostic.fixture is False
    assert diagnostic.processing_mode == "real_case" or diagnostic.processing_mode is None or diagnostic.source_kind == "uploaded_real_case"


def test_explicit_validated_fixture_backend_preserves_pipeline_contract(
    tmp_path, monkeypatch
) -> None:
    fixture = _write_artifact(tmp_path / "validated")
    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet_fixture")
    monkeypatch.setenv("ALIGNERSTUDIO_ALLOW_TEST_FIXTURE_BACKEND", "1")
    monkeypatch.setenv("ALIGNERSTUDIO_TOOTHINSTANCENET_VALIDATED_FIXTURE_DIR", str(fixture))

    # WP-01: fixture path must be hash-bound to the uploaded/artifact STL.
    diagnostic = process_uploaded_case(str(fixture / "upper.stl"), ArchType.UPPER)

    assert diagnostic.source_kind == "validated_real_case"
    assert diagnostic.fixture is True
    assert diagnostic.experimental is True
    assert diagnostic.processing_mode == "test_fixture"
    assert diagnostic.tooth_instance_count == 14
    assert diagnostic.excluded_fragment_count == 0
    assert diagnostic.fdi_assignments[0] == (0, None)
    assert not diagnostic.duplicate_fdi_numbers
    assert not diagnostic.missing_fdi_numbers
    assert diagnostic.state.value == "identification_incomplete"
