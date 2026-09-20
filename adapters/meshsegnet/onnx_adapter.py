"""ONNX Runtime adapter boundary prepared for legally-cleared MeshSegNet models.

This adapter contains no MeshSegNet source code and no weights. The exact
model input/output contract must be verified against a legally-cleared model
artifact before deployment.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from adapters.meshsegnet.contract import SegmentationModelContract, SegmentationModelContractError
from engines.segmentation.preprocessing import PreparedMesh


class SegmentationModelUnavailableError(RuntimeError):
    """Raised when an external segmentation model cannot be used."""


class OnnxRuntimeSegmentationAdapter:
    """Lazy ONNX Runtime adapter with configurable external model path."""

    def __init__(
        self,
        model_path: str | Path,
        *,
        model_name: str = "meshsegnet-onnx",
        model_version: str = "unversioned",
        contract: SegmentationModelContract | None = None,
        session: Any | None = None,
    ) -> None:
        self._model_path = Path(model_path)
        self._model_name = model_name
        self._model_version = model_version
        self._contract = contract
        self._session = session

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def model_version(self) -> str:
        return self._model_version

    def _get_session(self) -> Any:
        if self._session is not None:
            return self._session
        if not self._model_path.is_file():
            raise SegmentationModelUnavailableError(
                f"Segmentation model is unavailable at '{self._model_path}'. "
                "Provide a legally-cleared ONNX model path; no fallback segmentation is used."
            )
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise SegmentationModelUnavailableError(
                "onnxruntime is not installed. Install the optional ML segmentation dependency "
                "before enabling a real segmentation model."
            ) from exc
        self._session = ort.InferenceSession(
            str(self._model_path), providers=["CPUExecutionProvider"]
        )
        return self._session

    def infer(self, prepared_mesh: PreparedMesh) -> tuple[object, ...]:
        if self._contract is None:
            raise SegmentationModelUnavailableError(
                "Segmentation model contract is unavailable. "
                "A verified external contract is required."
            )
        try:
            self._contract.validate()
        except SegmentationModelContractError as error:
            raise SegmentationModelUnavailableError(str(error)) from error
        session = self._get_session()
        inputs = session.get_inputs()
        if not inputs:
            raise SegmentationModelUnavailableError("ONNX model exposes no input tensors")
        if len(inputs) != 1 or inputs[0].name != self._contract.input_name:
            raise SegmentationModelUnavailableError(
                "ONNX input tensors do not match the verified model contract."
            )
        try:
            return tuple(
                session.run(
                    None, {self._contract.input_name: prepared_mesh.face_features[None, ...]}
                )
            )
        except Exception as exc:  # noqa: BLE001 - make model contract errors actionable
            raise SegmentationModelUnavailableError(
                "ONNX segmentation inference failed. Verify the model's input contract "
                "matches the prepared face features."
            ) from exc
