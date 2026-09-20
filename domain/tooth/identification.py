"""Domain models for tooth identification and local coordinate systems."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from domain.case.provenance import DataProvenance
from domain.tooth.segmentation import ToothInstance

Vector3 = tuple[float, float, float]
Matrix3 = tuple[Vector3, Vector3, Vector3]


class ArchType(str, Enum):
    """The externally supplied arch context for an identification run."""

    UPPER = "upper"
    LOWER = "lower"


class IdentificationStatus(str, Enum):
    """Confidence state of one geometric identification result."""

    IDENTIFIED = "identified"
    UNCERTAIN = "uncertain"
    UNIDENTIFIED = "unidentified"


@dataclass(frozen=True)
class FDIToothIdentity:
    """Validated permanent-tooth FDI identity, separate from segmentation."""

    number: int
    arch: ArchType
    quadrant: int
    position_from_midline: int

    def __post_init__(self) -> None:
        if (
            self.number not in range(11, 19)
            and self.number not in range(21, 29)
            and self.number not in range(31, 39)
            and self.number not in range(41, 49)
        ):
            raise ValueError(f"Invalid permanent-tooth FDI number: {self.number}")
        if self.arch is ArchType.UPPER and self.quadrant not in (1, 2):
            raise ValueError("Upper arch identities must use quadrant 1 or 2")
        if self.arch is ArchType.LOWER and self.quadrant not in (3, 4):
            raise ValueError("Lower arch identities must use quadrant 3 or 4")
        if not 1 <= self.position_from_midline <= 8:
            raise ValueError("FDI position from midline must be between 1 and 8")


@dataclass(frozen=True)
class IdentificationConfidence:
    """Deterministic geometric confidence, not clinical confidence."""

    score: float
    status: IdentificationStatus
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("Identification confidence must be between 0 and 1")


@dataclass(frozen=True)
class ToothLandmarks:
    """Descriptive landmarks derived from the segmented surface geometry."""

    centroid: Vector3
    mesial_point: Vector3
    distal_point: Vector3
    occlusal_point: Vector3
    gingival_point: Vector3


@dataclass(frozen=True)
class ToothCoordinateSystem:
    """Stable orthonormal local frame for future movement representation."""

    origin: Vector3
    lateral_axis: Vector3
    anterior_axis: Vector3
    vertical_axis: Vector3
    semantics: tuple[str, str, str] = (
        "lateral/mesiodistal",
        "anterior/buccolingual",
        "vertical/occlusogingival",
    )


@dataclass(frozen=True)
class IdentifiedTooth:
    """A segmentation instance with optional geometric identity and frame."""

    instance: ToothInstance
    identity: FDIToothIdentity | None
    landmarks: ToothLandmarks | None
    coordinate_system: ToothCoordinateSystem | None
    confidence: IdentificationConfidence
    provenance: DataProvenance
    fixture: bool
    notes: str = ""


@dataclass(frozen=True)
class ToothIdentificationResult:
    """All identified/uncertain/unidentified instances for one arch."""

    arch: ArchType
    teeth: tuple[IdentifiedTooth, ...]
    provenance: DataProvenance
    fixture: bool
    notes: str = ""

    @property
    def identified(self) -> tuple[IdentifiedTooth, ...]:
        return tuple(
            tooth
            for tooth in self.teeth
            if tooth.confidence.status is IdentificationStatus.IDENTIFIED
        )

    @property
    def uncertain(self) -> tuple[IdentifiedTooth, ...]:
        return tuple(
            tooth
            for tooth in self.teeth
            if tooth.confidence.status is IdentificationStatus.UNCERTAIN
        )

    @property
    def unidentified(self) -> tuple[IdentifiedTooth, ...]:
        return tuple(
            tooth
            for tooth in self.teeth
            if tooth.confidence.status is IdentificationStatus.UNIDENTIFIED
        )
