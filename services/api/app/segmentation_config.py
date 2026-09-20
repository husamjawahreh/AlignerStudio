"""Environment-only configuration for an externally supplied segmentation model."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from adapters.meshsegnet.contract import SegmentationModelContract
from adapters.meshsegnet.onnx_adapter import OnnxRuntimeSegmentationAdapter


class SegmentationConfigurationError(ValueError):
    """Raised when real segmentation has not been fully configured."""


@dataclass(frozen=True)
class SegmentationConfiguration:
    model_path: Path
    contract_path: Path
    model_name: str
    model_version: str
    contract: SegmentationModelContract

    def adapter(self) -> OnnxRuntimeSegmentationAdapter:
        return OnnxRuntimeSegmentationAdapter(
            self.model_path,
            model_name=self.model_name,
            model_version=self.model_version,
            contract=self.contract,
        )


def load_segmentation_configuration() -> SegmentationConfiguration:
    model = os.environ.get("ALIGNERSTUDIO_SEGMENTATION_MODEL")
    contract = os.environ.get("ALIGNERSTUDIO_SEGMENTATION_CONTRACT")
    if not model or not contract:
        raise SegmentationConfigurationError(
            "Real segmentation is unavailable: set ALIGNERSTUDIO_SEGMENTATION_MODEL and "
            "ALIGNERSTUDIO_SEGMENTATION_CONTRACT. No fixture fallback is used."
        )
    model_path, contract_path = Path(model), Path(contract)
    if not model_path.is_file():
        raise SegmentationConfigurationError(
            "Configured segmentation model artifact is unavailable."
        )
    verified = SegmentationModelContract.load(contract_path)
    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
    if digest != verified.model_sha256:
        raise SegmentationConfigurationError(
            "Configured model SHA-256 does not match verified contract."
        )
    return SegmentationConfiguration(
        model_path=model_path,
        contract_path=contract_path,
        model_name=os.environ.get("ALIGNERSTUDIO_SEGMENTATION_MODEL_NAME", "external-onnx"),
        model_version=os.environ.get("ALIGNERSTUDIO_SEGMENTATION_MODEL_VERSION", "unversioned"),
        contract=verified,
    )
