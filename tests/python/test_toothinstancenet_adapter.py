import hashlib
from pathlib import Path

import numpy as np
import pytest

from adapters.toothinstancenet.contract import (
    ToothInstanceNetConfig,
    ToothInstanceNetConfigurationError,
    ToothInstanceNetUnavailableError,
    verified_fdi_number,
)
from adapters.toothinstancenet.preprocessing import prepare_mesh

FIXTURE = Path(__file__).parents[1] / "fixtures" / "synthetic_segmentation_arch.obj"


def artifact_config(tmp_path: Path, payload: bytes = b"checkpoint") -> ToothInstanceNetConfig:
    artifact = tmp_path / "instseg_full.ckpt"
    artifact.write_bytes(payload)
    return ToothInstanceNetConfig(
        checkpoint_path=artifact,
        checkpoint_sha256=hashlib.sha256(payload).hexdigest(),
    )


def test_checkpoint_hash_verification(tmp_path: Path) -> None:
    config = artifact_config(tmp_path)
    assert config.verify_checkpoint() == config.checkpoint_sha256


def test_missing_checkpoint_fails(tmp_path: Path) -> None:
    config = ToothInstanceNetConfig(checkpoint_path=tmp_path / "missing.ckpt")
    with pytest.raises(ToothInstanceNetUnavailableError, match="unavailable"):
        config.verify_checkpoint()


def test_environment_configuration_requires_explicit_artifact(monkeypatch) -> None:
    monkeypatch.delenv("ALIGNERSTUDIO_TOOTHINSTANCENET_CHECKPOINT", raising=False)
    with pytest.raises(ToothInstanceNetUnavailableError, match="CHECKPOINT"):
        ToothInstanceNetConfig.from_environment()


def test_invalid_checkpoint_hash_fails(tmp_path: Path) -> None:
    config = ToothInstanceNetConfig(
        checkpoint_path=tmp_path / "model.ckpt", checkpoint_sha256="0" * 64
    )
    config.checkpoint_path.write_bytes(b"wrong")
    with pytest.raises(ToothInstanceNetUnavailableError, match="SHA-256"):
        config.verify_checkpoint()


def test_source_revision_must_match(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    config = artifact_config(tmp_path)
    config = ToothInstanceNetConfig(
        checkpoint_path=config.checkpoint_path,
        checkpoint_sha256=config.checkpoint_sha256,
        source_root=source,
    )
    with pytest.raises(ToothInstanceNetUnavailableError, match="Git checkout"):
        config.verify_source_revision()


def test_configuration_rejects_contract_drift(tmp_path: Path) -> None:
    config = artifact_config(tmp_path)
    invalid = config.__class__(
        checkpoint_path=config.checkpoint_path,
        checkpoint_sha256=config.checkpoint_sha256,
        num_classes=8,
    )
    with pytest.raises(ToothInstanceNetConfigurationError, match="num_classes"):
        invalid.verify_checkpoint()


def test_preprocessing_produces_six_features_and_original_mapping(tmp_path: Path) -> None:
    prepared = prepare_mesh(FIXTURE, artifact_config(tmp_path))
    assert prepared.features.shape[1] == 6
    assert prepared.original_vertices.shape[0] == prepared.transformed_points.shape[0]
    assert len(np.unique(prepared.sampled_indices)) == len(prepared.sampled_indices)


def test_official_seven_class_fdi_mapping() -> None:
    assert verified_fdi_number(0, lower=False) == 11
    assert verified_fdi_number(6, lower=True) == 37
    assert verified_fdi_number(7, lower=False) is None
