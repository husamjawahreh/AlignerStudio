"""Anatomy extent boundary: crown-only STL vs future CBCT/DICOM root/bone."""

from __future__ import annotations

from enum import Enum


class AnatomyExtent(str, Enum):
    """What anatomical structures are genuinely represented in source data.

    Crown-only STL must never be treated as containing roots, bone, or
    periodontal structures. ROOT_BONE_CBCT is reserved for a future pathway
    when genuine CBCT/DICOM data is available.
    """

    CROWN_ONLY_STL = "crown_only_stl"
    ROOT_BONE_CBCT = "root_bone_cbct"


def default_anatomy_extent_for_stl() -> AnatomyExtent:
    """STL scan imports are crown-surface data only."""
    return AnatomyExtent.CROWN_ONLY_STL
