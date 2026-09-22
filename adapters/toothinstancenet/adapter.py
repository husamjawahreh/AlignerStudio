"""Isolated ToothInstanceNet runtime adapter.

The upstream source checkout and checkpoint are external runtime artifacts. No
weights are downloaded, and model-specific imports remain lazy and isolated.
"""

from __future__ import annotations

import importlib
import time
from pathlib import Path
from typing import Any

import numpy as np

from adapters.toothinstancenet.contract import (
    ToothInstanceNetConfig,
    ToothInstanceNetRawOutput,
    ToothInstanceNetUnavailableError,
)
from adapters.toothinstancenet.preprocessing import PreparedToothInstanceNetMesh


class ToothInstanceNetAdapter:
    """Construct and run the verified DentalNet instance-segmentation contract."""

    def __init__(self, config: ToothInstanceNetConfig) -> None:
        self.config = config
        self._model: Any | None = None
        self._torch: Any | None = None
        self._learned_region_cluster: Any | None = None
        self.runtime_metadata: dict[str, Any] = {}

    @property
    def model_name(self) -> str:
        return self.config.model_name

    @property
    def model_version(self) -> str:
        return self.config.model_version

    def _import_upstream(self) -> tuple[Any, Any, Any]:
        if self.config.source_root is None:
            raise ToothInstanceNetUnavailableError(
                "ToothInstanceNet source_root is not configured; no model source "
                "is downloaded automatically."
            )
        import sys

        self.config.verify_source_revision()
        source = str(Path(self.config.source_root).resolve())
        if source not in sys.path:
            sys.path.insert(0, source)
        try:
            torch = importlib.import_module("torch")
            point_tensor = importlib.import_module("teethland").PointTensor
            dental_net = importlib.import_module("teethland.models.dentalnet").DentalNet
            cluster = importlib.import_module("teethland.cluster").learned_region_cluster
        except Exception as exc:  # noqa: BLE001 - make optional runtime failures explicit
            raise ToothInstanceNetUnavailableError(
                "ToothInstanceNet runtime dependencies/source are unavailable. "
                "Install the verified upstream environment and configure source_root."
            ) from exc
        self._torch = torch
        self._learned_region_cluster = cluster
        return torch, point_tensor, dental_net

    def _build_model(self) -> Any:
        if self._model is not None:
            return self._model
        checkpoint_sha256 = self.config.verify_checkpoint()
        torch, _, dental_net = self._import_upstream()
        device = self._device(torch)
        model = dental_net(
            lr=0.0006,
            weight_decay=0.0001,
            epochs=200,
            warmup_epochs=5,
            in_channels=self.config.in_channels,
            num_classes=self.config.num_classes,
            channels_list=list(self.config.channels_list),
            depths=list(self.config.depths),
            heads_list=list(self.config.heads_list),
            window_sizes=list(self.config.window_sizes),
            point_embedding={
                "use": self.config.point_embedding_use,
                "kpconv_point_influence": self.config.kpconv_point_influence,
                "kpconv_ball_radius": self.config.kpconv_ball_radius,
            },
            stratified_union=self.config.stratified_union,
            downsample_ratio=self.config.downsample_ratio,
            max_drop_path_prob=self.config.max_drop_path_prob,
            stratified_downsample_ratio=self.config.stratified_downsample_ratio,
            crpe_bins=self.config.crpe_bins,
            transformer_lr_ratio=self.config.transformer_lr_ratio,
        )
        checkpoint = torch.load(
            self.config.checkpoint_path, map_location=device, weights_only=False
        )
        state_dict = checkpoint.get("state_dict", checkpoint)
        missing, unexpected = model.load_state_dict(state_dict, strict=False)
        if missing or unexpected:
            raise ToothInstanceNetUnavailableError(
                "ToothInstanceNet checkpoint does not match DentalNet exactly; "
                f"missing={list(missing)[:5]}, unexpected={list(unexpected)[:5]}"
            )
        model.to(device).eval()
        model._alignerstudio_checkpoint_sha256 = checkpoint_sha256
        self.runtime_metadata.update(
            {
                "model_constructed": True,
                "checkpoint_loaded": True,
                "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
                "device": str(device),
                "checkpoint_sha256": checkpoint_sha256,
            }
        )
        self._model = model
        return model

    def _device(self, torch: Any) -> Any:
        if self.config.device == "auto":
            return torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if self.config.device == "cuda" and not torch.cuda.is_available():
            raise ToothInstanceNetUnavailableError(
                "CUDA was explicitly requested but is unavailable."
            )
        return torch.device(self.config.device)

    def infer(
        self,
        prepared: PreparedToothInstanceNetMesh,
        *,
        lower: bool = False,
    ) -> ToothInstanceNetRawOutput:
        model = self._build_model()
        torch, point_tensor, _ = self._import_upstream()
        device = self._device(torch)
        coordinates = torch.from_numpy(prepared.transformed_points[prepared.sampled_indices]).to(
            device
        )
        features = torch.from_numpy(prepared.features).to(device)
        points = point_tensor(
            coordinates=coordinates,
            features=features,
            batch_counts=torch.tensor([len(coordinates)], device=device, dtype=torch.int64),
        )
        with torch.inference_mode():
            cluster_start = time.perf_counter()
            _, (spatial_embeds, seeds, learned_features) = model.instance_model(points)
            offsets = spatial_embeds.new_tensor(features=spatial_embeds.F[:, :3])
            sigmas = spatial_embeds.new_tensor(features=spatial_embeds.F[:, 3:])
            clusters = self._learned_region_cluster(offsets, sigmas, seeds)
            self.runtime_metadata["instance_model_executed"] = True
            self.runtime_metadata["learned_region_cluster_executed"] = True
            if not lower:
                clusters._coordinates[clusters.batch_counts[0]:, 0] *= -1
                self.runtime_metadata["upper_coordinate_flip_before_fdi"] = True
            _, class_scores = model.identify_model(learned_features, clusters)
            self.runtime_metadata["clustering_and_fdi_seconds"] = (
                time.perf_counter() - cluster_start
            )
            original_points = point_tensor(
                coordinates=torch.from_numpy(prepared.transformed_points).to(device),
                features=torch.from_numpy(
                    np.concatenate(
                        (prepared.transformed_points, prepared.transformed_normals), axis=1
                    )
                ).to(device),
                batch_counts=torch.tensor(
                    [len(prepared.transformed_points)], device=device, dtype=torch.int64
                ),
            )
            interpolated = clusters.interpolate(original_points)
            instance_labels = interpolated.F.detach().cpu().numpy().astype(np.int64)
            class_labels = (
                torch.argmax(class_scores.F, dim=-1).detach().cpu().numpy().astype(np.int64)
            )
            class_confidences = (
                torch.softmax(class_scores.F, dim=-1).max(dim=-1).values.detach().cpu().numpy()
            )
        if torch.cuda.is_available():
            self.runtime_metadata["peak_gpu_memory_bytes"] = int(
                torch.cuda.max_memory_allocated(device)
            )
        return ToothInstanceNetRawOutput(
            instance_labels=instance_labels,
            class_labels=class_labels,
            class_confidences=class_confidences,
            original_vertices=prepared.original_vertices,
            original_faces=prepared.original_faces,
            transformed_points=prepared.transformed_points,
            sampled_indices=prepared.sampled_indices,
            checkpoint_sha256=model._alignerstudio_checkpoint_sha256,
        )
