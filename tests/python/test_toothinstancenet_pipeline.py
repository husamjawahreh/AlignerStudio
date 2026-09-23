from app.pipeline_diagnostics import process_uploaded_case

from domain.tooth.identification import ArchType
from tests.python.test_toothinstancenet_fixture import _write_artifact


def test_validated_fixture_requires_explicit_backend_selection(tmp_path, monkeypatch) -> None:
    fixture = _write_artifact(tmp_path / "validated")
    monkeypatch.setenv("ALIGNERSTUDIO_TOOTHINSTANCENET_VALIDATED_FIXTURE_DIR", str(fixture))
    monkeypatch.delenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", raising=False)

    diagnostic = process_uploaded_case("not-used-by-default-backend.stl", ArchType.UPPER)

    assert diagnostic.state.value == "model_unavailable"
    assert diagnostic.fixture is False


def test_explicit_validated_fixture_backend_preserves_pipeline_contract(
    tmp_path, monkeypatch
) -> None:
    fixture = _write_artifact(tmp_path / "validated")
    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet_fixture")
    monkeypatch.setenv("ALIGNERSTUDIO_TOOTHINSTANCENET_VALIDATED_FIXTURE_DIR", str(fixture))

    diagnostic = process_uploaded_case("not-used-by-fixture-backend.stl", ArchType.UPPER)

    assert diagnostic.source_kind == "validated_real_case"
    assert diagnostic.fixture is True
    assert diagnostic.experimental is True
    assert diagnostic.tooth_instance_count == 14
    assert diagnostic.excluded_fragment_count == 0
    assert diagnostic.fdi_assignments[0] == (0, None)
    assert not diagnostic.duplicate_fdi_numbers
    assert not diagnostic.missing_fdi_numbers
    assert diagnostic.state.value == "identification_incomplete"
