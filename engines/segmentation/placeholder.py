"""Placeholder segmentation engine.

Returns a static fixture of FDI tooth labels. Does NOT analyze the mesh
geometry. Always tagged `generated` + `fixture=True` so callers cannot
mistake this for real segmentation. See TREATMENT_PLAN.md.
"""

from __future__ import annotations

from domain.tooth.models import FDI_TOOTH_NUMBERS, Tooth
from domain.treatment_plan.models import ToothPosition

FIXTURE_NOTE = (
    "Segmentation engine not yet implemented; returns a static FDI fixture "
    "set, not derived from mesh geometry."
)


class PlaceholderSegmentationEngine:
    """Fixture implementation of :class:`SegmentationEngine`."""

    def segment(self, mesh_file_path: str) -> tuple[ToothPosition, ...]:
        del mesh_file_path  # unused: fixture ignores the actual mesh content
        return tuple(ToothPosition(tooth=Tooth(fdi_number=n)) for n in sorted(FDI_TOOTH_NUMBERS))
