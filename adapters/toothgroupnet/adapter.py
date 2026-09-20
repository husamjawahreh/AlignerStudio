"""Adapter boundary for ToothGroupNetwork (https://github.com/limhoyeon/ToothGroupNetwork).

Not integrated in Phase 1 — see REUSE_MATRIX.md.
"""

from __future__ import annotations

from domain.treatment_plan.models import ToothPosition


class ToothGroupNetworkAdapter:
    """Adapter stub for ToothGroupNetwork. Not implemented — see REUSE_MATRIX.md."""

    def segment(self, mesh_file_path: str) -> tuple[ToothPosition, ...]:
        raise NotImplementedError(
            "ToothGroupNetwork is not integrated yet. See REUSE_MATRIX.md before implementing."
        )
