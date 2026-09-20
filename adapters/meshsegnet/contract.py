"""Verified external ONNX contract metadata; no model artifacts are stored here."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class SegmentationModelContractError(ValueError):
    """Raised when an external model contract is absent or incompatible."""


@dataclass(frozen=True)
class SegmentationModelContract:
    """The subset of a verified model contract supported by this adapter."""

    input_name: str
    input_layout: str
    feature_count: int
    requires_adjacency: bool
    output_mode: str
    background_label: int
    confidence_semantics: str
    license_verified: bool
    model_sha256: str

    @classmethod
    def load(cls, path: str | Path) -> SegmentationModelContract:
        try:
            payload = json.loads(Path(path).read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise SegmentationModelContractError(
                f"Unable to read segmentation contract '{path}'."
            ) from error
        try:
            contract = cls(**payload)
        except TypeError as error:
            raise SegmentationModelContractError(
                "Segmentation contract is missing required fields."
            ) from error
        contract.validate()
        return contract

    def validate(self) -> None:
        if not self.input_name.strip() or not self.model_sha256.strip():
            raise SegmentationModelContractError(
                "Model contract requires input_name and model_sha256."
            )
        if self.input_layout != "batch_face_features" or self.feature_count != 15:
            raise SegmentationModelContractError(
                "This adapter supports only batch_face_features with 15 ordered features."
            )
        if self.requires_adjacency:
            raise SegmentationModelContractError(
                "This adapter does not support models requiring adjacency tensors."
            )
        if self.output_mode not in {"face_labels", "face_scores"}:
            raise SegmentationModelContractError("Unsupported model output_mode.")
        if self.background_label != 0:
            raise SegmentationModelContractError(
                "The configured model must reserve label 0 for background."
            )
        if not self.confidence_semantics.strip() or not self.license_verified:
            raise SegmentationModelContractError(
                "Model license and confidence semantics must be explicitly verified."
            )
