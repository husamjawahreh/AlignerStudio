"""Production-oriented segmentation orchestration around an external adapter."""

from __future__ import annotations

from dataclasses import dataclass

from domain.case.provenance import DataProvenance
from domain.tooth.segmentation import ToothSegmentationResult
from engines.segmentation.interface import SegmentationInferenceAdapter
from engines.segmentation.output import build_segmentation_result, parse_model_outputs
from engines.segmentation.preprocessing import MeshPreprocessingConfig, prepare_mesh


@dataclass(frozen=True)
class OnnxSegmentationEngine:
    """Segmentation pipeline with explicit model availability and provenance."""

    adapter: SegmentationInferenceAdapter
    preprocessing: MeshPreprocessingConfig = MeshPreprocessingConfig()
    provenance: DataProvenance = DataProvenance.EXPERIMENTAL

    def segment(self, mesh_file_path: str) -> ToothSegmentationResult:
        prepared = prepare_mesh(mesh_file_path, self.preprocessing)
        raw_outputs = self.adapter.infer(prepared)
        parsed = parse_model_outputs(raw_outputs, len(prepared.faces))
        return build_segmentation_result(
            prepared,
            parsed,
            engine_name="onnx-segmentation",
            model_name=self.adapter.model_name,
            model_version=self.adapter.model_version,
            provenance=self.provenance,
        )
