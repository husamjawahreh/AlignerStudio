"""Explicit ToothInstanceNet backend configuration for the API composition root."""

from __future__ import annotations

import os
from pathlib import Path

from adapters.toothinstancenet.adapter import ToothInstanceNetAdapter
from adapters.toothinstancenet.contract import ToothInstanceNetConfig
from adapters.toothinstancenet.fixture import load_validated_fixture
from domain.tooth.identification import ArchType
from engines.segmentation.toothinstancenet import (
    ToothInstanceNetEngine,
    ToothInstanceNetInferenceResult,
)

from app.processing_modes import selected_backend

__all__ = [
    "ToothInstanceNetConfigurationError",
    "selected_backend",
    "load_toothinstancenet_engine",
    "load_validated_fixture_result",
]


class ToothInstanceNetConfigurationError(ValueError):
    """Raised when the explicitly selected ToothInstanceNet backend is incomplete."""


def load_toothinstancenet_engine(arch: ArchType) -> ToothInstanceNetEngine:
    try:
        config = ToothInstanceNetConfig.from_environment()
    except Exception as error:
        raise ToothInstanceNetConfigurationError(str(error)) from error
    return ToothInstanceNetEngine(ToothInstanceNetAdapter(config), arch=arch)


def load_validated_fixture_result(
    arch: ArchType, source_mesh_path: str | Path | None = None
) -> ToothInstanceNetInferenceResult:
    fixture_path = os.environ.get("ALIGNERSTUDIO_TOOTHINSTANCENET_VALIDATED_FIXTURE")
    fixture_dir = os.environ.get("ALIGNERSTUDIO_TOOTHINSTANCENET_VALIDATED_FIXTURE_DIR")
    if fixture_dir:
        fixture_path = fixture_dir
    if not fixture_path:
        raise ToothInstanceNetConfigurationError(
            "Validated fixture backend requires an explicit fixture file or fixture directory."
        )
    return load_validated_fixture(Path(fixture_path), arch=arch, source_mesh_path=source_mesh_path)
