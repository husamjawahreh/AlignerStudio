"""MeshSegNet adapter entry point.

Only the ONNX adapter boundary is provided. MeshSegNet source and weights are
not copied or bundled; see REUSE_MATRIX.md and REUSE_DECISION.md.
"""

from __future__ import annotations

from adapters.meshsegnet.onnx_adapter import (
    OnnxRuntimeSegmentationAdapter,
    SegmentationModelUnavailableError,
)

MeshSegNetAdapter = OnnxRuntimeSegmentationAdapter

__all__ = [
    "MeshSegNetAdapter",
    "OnnxRuntimeSegmentationAdapter",
    "SegmentationModelUnavailableError",
]
