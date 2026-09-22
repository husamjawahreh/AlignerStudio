import json

from app.pipeline_diagnostics import process_uploaded_case

from domain.tooth.identification import ArchType
from tests.python.test_toothinstancenet_fixture import artifact_payload


def test_validated_fixture_requires_explicit_backend_selection(tmp_path, monkeypatch) -> None:
    fixture = tmp_path / "validated.json"
    fixture.write_text(json.dumps(artifact_payload(count=1, fdis=[11])))
    monkeypatch.setenv("ALIGNERSTUDIO_TOOTHINSTANCENET_VALIDATED_FIXTURE", str(fixture))
    monkeypatch.delenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", raising=False)

    diagnostic = process_uploaded_case("not-used-by-default-backend.stl", ArchType.UPPER)

    assert diagnostic.state.value == "model_unavailable"
    assert diagnostic.fixture is False


def test_explicit_validated_fixture_backend_preserves_pipeline_contract(
    tmp_path, monkeypatch
) -> None:
    fixture = tmp_path / "validated.json"
    fixture.write_text(json.dumps(artifact_payload(count=28, fdis=[11] * 28)))
    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet_fixture")
    monkeypatch.setenv("ALIGNERSTUDIO_TOOTHINSTANCENET_VALIDATED_FIXTURE", str(fixture))

    diagnostic = process_uploaded_case("not-used-by-fixture-backend.stl", ArchType.UPPER)

    assert diagnostic.source_kind == "validated_real_case"
    assert diagnostic.fixture is True
    assert diagnostic.experimental is True
    assert diagnostic.tooth_instance_count == 28
    assert diagnostic.excluded_fragment_count == 1
    assert diagnostic.fdi_assignments[0] == (0, 11)
    assert diagnostic.duplicate_fdi_numbers
    assert diagnostic.missing_fdi_numbers
    assert diagnostic.state.value == "identification_incomplete"
