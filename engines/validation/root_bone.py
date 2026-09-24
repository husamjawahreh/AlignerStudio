"""CBCT/DICOM-gated root/bone pathway — architectural boundary only for P3.

Never infer roots, bone, or periodontal structures from crown-only STL.
Activation requires genuine CBCT/DICOM ingestion and AnatomyExtent.ROOT_BONE_CBCT.
"""

from __future__ import annotations

from domain.tooth.anatomy_extent import AnatomyExtent


class RootBonePathwayError(ValueError):
    """Raised when root/bone logic is requested without genuine CBCT evidence."""


def assert_root_bone_pathway_allowed(anatomy_extent: AnatomyExtent) -> None:
    """Gate for future root/bone-aware validation.

    Callers must not proceed when anatomy is crown-only STL.
    """
    if anatomy_extent is not AnatomyExtent.ROOT_BONE_CBCT:
        raise RootBonePathwayError(
            "Root/bone checks require genuine CBCT/DICOM anatomy extent; "
            "crown-only STL must not invent invisible anatomy."
        )


def root_bone_pathway_supported(anatomy_extent: AnatomyExtent) -> bool:
    return anatomy_extent is AnatomyExtent.ROOT_BONE_CBCT
