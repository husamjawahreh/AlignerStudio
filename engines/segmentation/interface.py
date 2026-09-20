"""Ports for production tooth segmentation."""

from __future__ import annotations

from typing import Protocol

from domain.tooth.segmentation import ToothSegmentationResult
from engines.segmentation.preprocessing import PreparedMesh


class SegmentationInferenceAdapter(Protocol):
    """Runs an external segmentation model without owning domain decisions."""

    @property
    def model_name(self) -> str:
        """Stable adapter/model identifier for provenance metadata."""
        ...

    @property
    def model_version(self) -> str:
        """Model version supplied by configuration or model metadata."""
        ...

    def infer(self, prepared_mesh: PreparedMesh) -> tuple[object, ...]:
        """Return raw model outputs; parsing remains in the engine layer."""
        ...


class SegmentationEngine(Protocol):
    """Produces geometry-only per-tooth segmentation results."""

    def segment(self, mesh_file_path: str) -> ToothSegmentationResult:
        """Validate, preprocess, infer, parse, and extract tooth instances."""
        ...
