"""Read a ToothInstanceNet checkpoint contract from its state dict.

The loader does not import PyTorch, pointops, or the teethland package, and it
does not run a forward pass. Tensor shapes come from the checkpoint pickle.
Class names are not inferred from filenames.
"""

from __future__ import annotations

import io
import pickle
import zipfile
from collections import OrderedDict
from pathlib import Path
from typing import Any


class CheckpointLoadError(RuntimeError):
    """The checkpoint file could not be read as a state dict."""


class _FakeStorage:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.numel = args[0] if args else None

    def __setstate__(self, state: Any) -> None:
        self.state = state


class _FloatStorage(_FakeStorage):
    dtype = "float32"


class _LongStorage(_FakeStorage):
    dtype = "int64"


def _rebuild_tensor_v2(
    storage: Any,
    storage_offset: int,
    size: Any,
    stride: Any,
    requires_grad: bool,
    backward_hooks: Any,
    metadata: Any = None,
) -> dict[str, Any]:
    return {
        "kind": "tensor",
        "shape": tuple(int(item) for item in size),
        "stride": tuple(int(item) for item in stride),
        "offset": int(storage_offset),
        "storage_type": type(storage).__name__,
    }


class _Stub:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs

    def __setstate__(self, state: Any) -> None:
        self.state = state

    def __setitem__(self, key: Any, value: Any) -> None:
        stored = getattr(self, "items_set", None)
        if stored is None:
            stored = {}
            self.items_set = stored
        stored[key] = value


class _CheckpointUnpickler(pickle.Unpickler):
    """Rebuild tensor metadata and refuse to execute checkpoint code."""

    def __init__(self, stream: io.BytesIO) -> None:
        super().__init__(stream)
        self._types: dict[str, type] = {}

    def find_class(self, module: str, name: str) -> Any:
        if module == "collections" and name == "OrderedDict":
            return OrderedDict
        if module == "torch" and name == "FloatStorage":
            return _FloatStorage
        if module == "torch" and name == "LongStorage":
            return _LongStorage
        if module == "torch._utils" and name == "_rebuild_tensor_v2":
            return _rebuild_tensor_v2
        key = f"{module}.{name}"
        if key not in self._types:
            self._types[key] = type(name, (_Stub,), {"__module__": module, "__qualname__": key})
        return self._types[key]

    def persistent_load(self, pid: Any) -> tuple[str, Any]:
        return ("PERSIST", pid)


def load_checkpoint_object(path: Path) -> dict[str, Any]:
    """Load checkpoint metadata. Does not restore weight values or run the model."""
    if not path.is_file():
        raise CheckpointLoadError(f"Checkpoint is not a file: {path}")
    if not zipfile.is_zipfile(path):
        raise CheckpointLoadError("Checkpoint is not a PyTorch zip archive.")
    with zipfile.ZipFile(path) as archive:
        try:
            payload = archive.read("archive/data.pkl")
        except KeyError as exc:
            raise CheckpointLoadError("Checkpoint zip has no archive/data.pkl.") from exc
    try:
        loaded = _CheckpointUnpickler(io.BytesIO(payload)).load()
    except (pickle.UnpicklingError, ValueError, TypeError, EOFError) as exc:
        raise CheckpointLoadError(f"Checkpoint pickle could not be read: {exc}") from exc
    if not isinstance(loaded, dict) or not isinstance(loaded.get("state_dict"), dict):
        raise CheckpointLoadError("Checkpoint pickle has no state_dict.")
    return loaded


def _tensor(state: dict[str, Any], key: str) -> dict[str, Any] | None:
    value = state.get(key)
    if isinstance(value, dict) and value.get("kind") == "tensor":
        return value
    return None


def _class_count_formula(class_count: int) -> dict[str, Any]:
    """Record the only TeethInstSegDataModule.num_classes setting that yields this count.

    The function is factor * (7 if m3_as_m2 else 8), where factor doubles for
    left/right and again for upper/lower. This is a formula fit, not a config
    stored in the checkpoint.
    """
    fits_collapsed_seven = class_count == 7
    return {
        "source": "teethland/datamodules/teethinstseg.py num_classes",
        "observed_outputs": class_count,
        "only_setting_that_returns_7": {
            "distinguish_left_right": False,
            "m3_as_m2": True,
            "upper_lower_doubled": False,
        },
        "matches_that_setting": fits_collapsed_seven,
        "stored_in_checkpoint": False,
    }


def extract_contract_from_loaded(loaded: dict[str, Any]) -> dict[str, Any]:
    """Derive the tensor contract from a loaded checkpoint object."""
    state = loaded["state_dict"]
    tensors = {
        key: value
        for key, value in state.items()
        if isinstance(value, dict) and value.get("kind") == "tensor"
    }
    first_weight = _tensor(tensors, "instance_model.point_embedding.0.kpconv.weight")
    kernel_points = _tensor(tensors, "instance_model.point_embedding.0.kpconv.K_points")
    head0 = _tensor(tensors, "instance_model.heads.0.linear.weight")
    head1 = _tensor(tensors, "instance_model.heads.1.linear.weight")
    identify_in = _tensor(tensors, "identify_model.mlp.0.weight")
    identify_mid = _tensor(tensors, "identify_model.mlp.2.weight")
    identify_out = _tensor(tensors, "identify_model.mlp.4.weight")
    identify_bias = _tensor(tensors, "identify_model.mlp.4.bias")
    required = (first_weight, kernel_points, head0, head1, identify_in, identify_mid, identify_out)
    if any(item is None for item in required):
        return {
            "state": "MODEL_CONTRACT_UNKNOWN",
            "tensor_contract_rederived": False,
            "reason": "The state dict does not contain the DentalNet tensors used as the contract.",
            "tensor_count": len(tensors),
            "top_level_keys": sorted(loaded.keys()),
        }
    assert first_weight is not None
    assert kernel_points is not None
    assert head0 is not None
    assert head1 is not None
    assert identify_in is not None
    assert identify_mid is not None
    assert identify_out is not None
    in_channels = int(first_weight["shape"][1]) if len(first_weight["shape"]) == 3 else None
    class_count = int(identify_out["shape"][0]) if identify_out["shape"] else None
    head2_present = any(key.startswith("instance_model.heads.2.") for key in tensors)
    identity_keys = [
        key
        for key in tensors
        if any(token in key.lower() for token in ("fdi", "arch", "left", "right"))
    ]
    established = (
        in_channels == 6
        and kernel_points["shape"] == (15, 3)
        and first_weight["shape"] == (15, 6, 48)
        and head0["shape"] == (6, 48)
        and head1["shape"] == (1, 48)
        and identify_in["shape"] == (64, 48)
        and identify_mid["shape"] == (64, 64)
        and identify_out["shape"] == (7, 64)
        and identify_bias is not None
        and identify_bias["shape"] == (7,)
        and not head2_present
        and not identity_keys
    )
    return {
        "state": "TENSOR_CONTRACT_ESTABLISHED" if established else "MODEL_CONTRACT_UNKNOWN",
        "tensor_contract_rederived": established,
        "label_names_stored_in_checkpoint": False,
        "reason": (
            "Tensor shapes were read from the checkpoint state dict. "
            "Class names are not stored in the file."
            if established
            else "Loaded tensors do not match the DentalNet shape contract."
        ),
        "architecture": {
            "name": "DentalNet",
            "evidence": "state_dict prefixes instance_model.* and identify_model.*",
            "lightning_version": loaded.get("pytorch-lightning_version"),
            "epoch": loaded.get("epoch"),
            "global_step": loaded.get("global_step"),
            "hyper_parameters_present": "hyper_parameters" in loaded or "hparams" in loaded,
        },
        "tensor_count": len(tensors),
        "input": {
            "representation": "variable-size point cloud",
            "fixed_point_count": None,
            "in_channels": in_channels,
            "kernel_points": int(kernel_points["shape"][0]),
            "spatial_dimension": int(kernel_points["shape"][1]),
            "first_kpconv_weight_shape": list(first_weight["shape"]),
            "weight_layout": "[n_kernel_points, num_inputs, num_outputs]",
            "weight_layout_source": (
                "teethland/nn/modules/torch_points3d.py KPConvLayer at the pinned source revision"
            ),
        },
        "instance_head": {
            "head0_shape": list(head0["shape"]),
            "head0_meaning": "3 spatial offsets concatenated with 3 sigmas",
            "head0_meaning_source": "teethland/models/dentalnet.py out_channels=[6, 1, None]",
            "head1_shape": list(head1["shape"]),
            "head1_meaning": "one seed logit",
            "feature_head_weights_present": head2_present,
            "feature_width": int(identify_in["shape"][1]),
        },
        "identify_head": {
            "mlp_shapes": [
                list(identify_in["shape"]),
                list(identify_mid["shape"]),
                list(identify_out["shape"]),
            ],
            "out_channels": class_count,
            "applied_to": "masked average of instance features, not a per-vertex semantic map",
            "source": "teethland/nn/modules/pooling.py MaskedAveragePooling",
        },
        "output": {
            "kind": "instance segmentation plus a per-instance classification head",
            "semantic_segmentation_map": False,
            "instance_ids_generated_by_network": False,
            "instance_ids_generated_by": "teethland.cluster.learned_region_cluster",
            "tooth_identity_encoded": False,
            "arch_encoded": False,
            "left_right_encoded": False,
            "fdi_encoded": False,
            "identity_key_matches": identity_keys,
        },
        "preprocessing_stored_in_checkpoint": False,
        "class_count_formula": _class_count_formula(class_count or 0),
        "evidence_keys": [
            "instance_model.point_embedding.0.kpconv.weight",
            "instance_model.point_embedding.0.kpconv.K_points",
            "instance_model.heads.0.linear.weight",
            "instance_model.heads.1.linear.weight",
            "identify_model.mlp.0.weight",
            "identify_model.mlp.2.weight",
            "identify_model.mlp.4.weight",
            "identify_model.mlp.4.bias",
        ],
    }


def extract_checkpoint_contract(path: Path) -> dict[str, Any]:
    try:
        loaded = load_checkpoint_object(path)
    except CheckpointLoadError as exc:
        return {
            "state": "MODEL_LOAD_FAILED",
            "tensor_contract_rederived": False,
            "reason": str(exc),
            "path": str(path),
        }
    contract = extract_contract_from_loaded(loaded)
    contract["path"] = str(path)
    return contract
