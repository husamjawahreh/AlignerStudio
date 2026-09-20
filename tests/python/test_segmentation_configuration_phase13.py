import hashlib
import json

import pytest
from app.segmentation_config import SegmentationConfigurationError, load_segmentation_configuration

from adapters.meshsegnet.contract import SegmentationModelContract, SegmentationModelContractError


def contract_payload(model_sha256: str, **overrides: object) -> dict[str, object]:
    return {
        "input_name": "face_features",
        "input_layout": "batch_face_features",
        "feature_count": 15,
        "requires_adjacency": False,
        "output_mode": "face_scores",
        "background_label": 0,
        "confidence_semantics": "softmax maximum per face",
        "license_verified": True,
        "model_sha256": model_sha256,
        **overrides,
    }


def test_real_model_configuration_requires_environment(monkeypatch) -> None:
    monkeypatch.delenv("ALIGNERSTUDIO_SEGMENTATION_MODEL", raising=False)
    monkeypatch.delenv("ALIGNERSTUDIO_SEGMENTATION_CONTRACT", raising=False)
    with pytest.raises(SegmentationConfigurationError, match="No fixture fallback"):
        load_segmentation_configuration()


def test_real_model_configuration_verifies_contract_and_artifact_hash(
    tmp_path, monkeypatch
) -> None:
    artifact = tmp_path / "cleared-model.onnx"
    artifact.write_bytes(b"externally supplied model bytes")
    contract = tmp_path / "model-contract.json"
    contract.write_text(
        json.dumps(contract_payload(hashlib.sha256(artifact.read_bytes()).hexdigest()))
    )
    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_MODEL", str(artifact))
    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_CONTRACT", str(contract))
    configuration = load_segmentation_configuration()
    assert configuration.contract.feature_count == 15
    assert configuration.contract.model_sha256 == hashlib.sha256(artifact.read_bytes()).hexdigest()


def test_contract_rejects_models_requiring_unimplemented_adjacency() -> None:
    with pytest.raises(SegmentationModelContractError, match="adjacency"):
        SegmentationModelContract(**contract_payload("a" * 64, requires_adjacency=True)).validate()
