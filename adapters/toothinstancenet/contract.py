"""Configuration and raw output contracts for the official ToothInstanceNet runtime."""

from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ToothInstanceNetError(RuntimeError):
    """Base error for explicit ToothInstanceNet runtime failures."""


class ToothInstanceNetUnavailableError(ToothInstanceNetError):
    """Raised when the configured model runtime cannot be used."""

    state = "model_unavailable"


class ToothInstanceNetInferenceError(ToothInstanceNetError):
    """Raised when an available model cannot complete segmentation."""

    state = "segmentation_failed"


class ToothInstanceNetConfigurationError(ToothInstanceNetError):
    """Raised when the authoritative model contract is invalid."""


@dataclass(frozen=True)
class ToothInstanceNetConfig:
    """Exact model/runtime settings from the validated implementation contract."""

    checkpoint_path: Path
    checkpoint_sha256: str = "100c68a9b120402cc75539eff6347bd998bce8b1d4f01550638f471797d70803"
    source_root: Path | None = None
    source_revision: str = "424252e3d94a1565c8c2090eb5bb456b76386b93"
    device: str = "auto"
    model_name: str = "toothinstancenet"
    model_version: str = "3dteethland-424252e3d94a1565c8c2090eb5bb456b76386b93"
    in_channels: int = 6
    num_classes: int = 7
    uniform_density_voxel_size: float = 0.025
    zscore_std: float = 17.3281

    channels_list: tuple[int, ...] = (48, 96, 192, 256)
    depths: tuple[int, ...] = (3, 9, 3)
    heads_list: tuple[int, ...] = (6, 12, 24)
    window_sizes: tuple[float, ...] = (0.4, 0.8, 1.6)
    point_embedding_use: bool = True
    kpconv_point_influence: float = 0.04
    kpconv_ball_radius: float = 0.1
    stratified_union: bool = False
    downsample_ratio: float = 0.26
    max_drop_path_prob: float = 0.3
    stratified_downsample_ratio: float = 0.26
    crpe_bins: int = 80
    transformer_lr_ratio: float = 0.1

    @classmethod
    def from_environment(cls) -> ToothInstanceNetConfig:
        """Build configuration from explicit runtime settings; never downloads artifacts."""
        checkpoint = os.environ.get("ALIGNERSTUDIO_TOOTHINSTANCENET_CHECKPOINT")
        if not checkpoint:
            raise ToothInstanceNetUnavailableError(
                "Set ALIGNERSTUDIO_TOOTHINSTANCENET_CHECKPOINT to an externally "
                "supplied verified artifact."
            )
        source = os.environ.get("ALIGNERSTUDIO_TOOTHINSTANCENET_SOURCE")
        return cls(
            checkpoint_path=Path(checkpoint),
            source_root=Path(source) if source else None,
            device=os.environ.get("ALIGNERSTUDIO_TOOTHINSTANCENET_DEVICE", "auto"),
        )

    def validate(self) -> None:
        if self.num_classes != 7:
            raise ToothInstanceNetConfigurationError("ToothInstanceNet requires num_classes=7")
        if self.in_channels != 6:
            raise ToothInstanceNetConfigurationError("ToothInstanceNet requires in_channels=6")
        if self.channels_list != (48, 96, 192, 256):
            raise ToothInstanceNetConfigurationError(
                "channels_list does not match the verified contract"
            )
        if self.depths != (3, 9, 3) or self.heads_list != (6, 12, 24):
            raise ToothInstanceNetConfigurationError(
                "transformer depth/head configuration is not verified"
            )
        if self.window_sizes != (0.4, 0.8, 1.6):
            raise ToothInstanceNetConfigurationError(
                "window_sizes does not match the verified contract"
            )
        if self.uniform_density_voxel_size != 0.025 or self.zscore_std != 17.3281:
            raise ToothInstanceNetConfigurationError(
                "preprocessing values do not match the verified contract"
            )
        if len(self.checkpoint_sha256) != 64:
            raise ToothInstanceNetConfigurationError("checkpoint_sha256 must be a SHA-256 digest")
        if not self.checkpoint_path.is_file():
            raise ToothInstanceNetUnavailableError(
                f"ToothInstanceNet checkpoint is unavailable at '{self.checkpoint_path}'."
            )

    def verify_checkpoint(self) -> str:
        """Verify the artifact before any model import or checkpoint load."""
        self.validate()
        digest = hashlib.sha256(self.checkpoint_path.read_bytes()).hexdigest()
        if digest != self.checkpoint_sha256:
            raise ToothInstanceNetUnavailableError(
                "ToothInstanceNet checkpoint SHA-256 does not match the verified artifact."
            )
        return digest

    def verify_source_revision(self) -> str:
        if self.source_root is None:
            raise ToothInstanceNetUnavailableError(
                "ToothInstanceNet source_root is not configured."
            )
        try:
            revision = subprocess.check_output(
                ["git", "-C", str(self.source_root), "rev-parse", "HEAD"],
                text=True,
            ).strip()
        except Exception as exc:  # noqa: BLE001 - runtime boundary
            raise ToothInstanceNetUnavailableError(
                "ToothInstanceNet source checkout is unavailable or is not a Git checkout."
            ) from exc
        if revision != self.source_revision:
            raise ToothInstanceNetUnavailableError(
                f"ToothInstanceNet source revision {revision} does not match "
                f"the verified revision {self.source_revision}."
            )
        return revision


@dataclass(frozen=True)
class ToothInstanceNetRawOutput:
    """Model-level output before domain extraction or FDI diagnostics."""

    instance_labels: Any
    class_labels: Any
    class_confidences: Any
    original_vertices: Any
    original_faces: Any
    transformed_points: Any
    sampled_indices: Any
    checkpoint_sha256: str


@dataclass(frozen=True)
class ToothInstanceNetDiagnostics:
    """Non-mutating review diagnostics for model FDI assignments."""

    state: str
    fdi_by_instance: tuple[tuple[int, int | None], ...]
    duplicate_fdi_numbers: tuple[int, ...]
    missing_fdi_numbers: tuple[int, ...]
    empty_instance_ids: tuple[int, ...]
    notes: tuple[str, ...] = ()
    model_class_by_instance: tuple[tuple[int, int | None], ...] = ()
    label_semantics: str = "seven_class_semantic_not_unique_fdi"
    fdi_authoritative: bool = False
    output_class: str = "ENGINEERING_OUTPUT"
    clinical_accuracy_claim: bool = False


def verified_fdi_number(model_class: int, *, lower: bool) -> int | None:
    """Historical seven-class code, not an authoritative FDI number.

    The model emits one of seven semantic classes. This helper maps class 0–6
    onto 11–17 or 31–37 so older diagnostics can name that code. It does not
    distinguish left from right, and callers must not persist the result as
    FDIToothIdentity or as planning mode clinical_fdi.
    """
    if not 0 <= model_class < 7:
        return None
    return (31 if lower else 11) + model_class


def checkpoint_manifest(config: ToothInstanceNetConfig) -> dict[str, str]:
    """Return auditable artifact metadata without loading the checkpoint."""
    return {
        "path": str(config.checkpoint_path),
        "sha256": config.verify_checkpoint(),
        "model": config.model_name,
        "version": config.model_version,
    }
