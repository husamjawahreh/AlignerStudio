"""Deterministic geometric FDI identification, separate from segmentation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from domain.tooth.identification import (
    ArchType,
    FDIToothIdentity,
    IdentificationConfidence,
    IdentificationStatus,
    IdentifiedTooth,
    ToothCoordinateSystem,
    ToothIdentificationResult,
    ToothLandmarks,
)
from domain.tooth.segmentation import ToothSegmentationResult
from engines.arrangement.geometry import (
    ToothGeometryError,
    build_arch_axes,
    finite_vertices,
    landmarks_for_instance,
)


@dataclass(frozen=True)
class ToothIdentificationConfig:
    """Engineering ambiguity settings; no values are clinical thresholds."""

    lateral_ambiguity_tolerance: float = 1e-6


class ToothIdentificationEngine:
    """Identify complete, unambiguous arches using geometry and supplied arch type.

    Rule: a complete arch must contain exactly sixteen valid instances. The
    arch frame's lateral axis divides patient-right (negative) and patient-left
    (positive) halves. Each half must contain eight instances, ordered from the
    midline outward; those slots map to FDI positions 1 through 8. Any missing,
    malformed, duplicated, or midline-ambiguous geometry remains uncertain or
    unidentified and receives no FDI identity.
    """

    def __init__(self, config: ToothIdentificationConfig | None = None) -> None:
        self.config = config or ToothIdentificationConfig()

    def identify(
        self, segmentation: ToothSegmentationResult, arch: ArchType
    ) -> ToothIdentificationResult:
        valid: list[tuple[object, np.ndarray]] = []
        preliminary: dict[int, IdentifiedTooth] = {}
        for instance in segmentation.instances:
            try:
                vertices = finite_vertices(instance)
                preliminary[instance.instance_id] = self._unresolved(
                    instance, arch, segmentation, vertices
                )
                valid.append((instance, np.asarray(instance.centroid, dtype=np.float64)))
            except (ToothGeometryError, ValueError):
                preliminary[instance.instance_id] = self._unidentified(
                    instance, segmentation, "Missing or malformed tooth geometry."
                )

        if len(valid) < 2:
            return self._result(
                segmentation,
                arch,
                preliminary.values(),
                "Insufficient valid geometry for an arch frame.",
            )

        try:
            centroids = np.asarray([centroid for _, centroid in valid], dtype=np.float64)
            origin = tuple(float(value) for value in centroids.mean(axis=0).tolist())
            axes = build_arch_axes(centroids)
            lateral = np.asarray(axes[0])
            projected = [
                (
                    instance,
                    float(np.dot(np.asarray(instance.centroid) - centroids.mean(axis=0), lateral)),
                )
                for instance, _ in valid
            ]
        except (ToothGeometryError, ValueError):
            return self._result(
                segmentation, arch, preliminary.values(), "Unable to build a stable arch frame."
            )

        sides = {
            "right": sorted(
                (item for item in projected if item[1] < -self.config.lateral_ambiguity_tolerance),
                key=lambda item: abs(item[1]),
            ),
            "left": sorted(
                (item for item in projected if item[1] > self.config.lateral_ambiguity_tolerance),
                key=lambda item: abs(item[1]),
            ),
        }
        ambiguous = [
            item for item in projected if abs(item[1]) <= self.config.lateral_ambiguity_tolerance
        ]
        complete = (
            len(valid) == 16
            and len(sides["right"]) == 8
            and len(sides["left"]) == 8
            and not ambiguous
        )
        duplicate = any(
            np.isclose(first[1], second[1], atol=self.config.lateral_ambiguity_tolerance)
            for side in sides.values()
            for first, second in zip(side, side[1:], strict=False)
        )
        if not complete or duplicate:
            reason = "Arch does not provide sixteen unique, unambiguous geometric slots."
            for instance, _ in valid:
                preliminary[instance.instance_id] = self._uncertain(
                    instance, segmentation, reason, origin, axes
                )
            return self._result(segmentation, arch, preliminary.values(), reason)

        for side_name, quadrant in (
            ("right", 1 if arch is ArchType.UPPER else 4),
            ("left", 2 if arch is ArchType.UPPER else 3),
        ):
            for position, (instance, _) in enumerate(sides[side_name], start=1):
                identity = FDIToothIdentity(
                    number=quadrant * 10 + position,
                    arch=arch,
                    quadrant=quadrant,
                    position_from_midline=position,
                )
                landmarks = self._landmarks(instance, axes)
                preliminary[instance.instance_id] = IdentifiedTooth(
                    instance=instance,
                    identity=identity,
                    landmarks=landmarks,
                    coordinate_system=ToothCoordinateSystem(
                        origin=tuple(float(value) for value in instance.centroid),
                        lateral_axis=axes[0],
                        anterior_axis=axes[1],
                        vertical_axis=axes[2],
                    ),
                    confidence=IdentificationConfidence(
                        1.0, IdentificationStatus.IDENTIFIED, ("Complete geometric arch slot.",)
                    ),
                    provenance=segmentation.metadata.provenance,
                    fixture=segmentation.metadata.fixture or instance.fixture,
                )
        return self._result(
            segmentation,
            arch,
            preliminary.values(),
            "Deterministic geometric identification completed.",
        )

    def _landmarks(self, instance, axes) -> ToothLandmarks:
        centroid, minimum, maximum, occlusal, gingival = landmarks_for_instance(instance, axes)
        if centroid[0] >= 0:
            mesial, distal = minimum, maximum
        else:
            mesial, distal = maximum, minimum
        return ToothLandmarks(centroid, mesial, distal, occlusal, gingival)

    def _unresolved(self, instance, arch, segmentation, vertices):
        del arch, vertices
        return IdentifiedTooth(
            instance,
            None,
            None,
            None,
            IdentificationConfidence(
                0.0, IdentificationStatus.UNCERTAIN, ("Arch slot has not been resolved.",)
            ),
            segmentation.metadata.provenance,
            segmentation.metadata.fixture or instance.fixture,
        )

    def _uncertain(self, instance, segmentation, reason, origin=None, axes=None):
        frame = (
            None
            if axes is None
            else ToothCoordinateSystem(
                tuple(float(value) for value in instance.centroid), axes[0], axes[1], axes[2]
            )
        )
        landmarks = None if axes is None else self._landmarks(instance, axes)
        return IdentifiedTooth(
            instance,
            None,
            landmarks,
            frame,
            IdentificationConfidence(0.5, IdentificationStatus.UNCERTAIN, (reason,)),
            segmentation.metadata.provenance,
            segmentation.metadata.fixture or instance.fixture,
        )

    def _unidentified(self, instance, segmentation, reason):
        return IdentifiedTooth(
            instance,
            None,
            None,
            None,
            IdentificationConfidence(0.0, IdentificationStatus.UNIDENTIFIED, (reason,)),
            segmentation.metadata.provenance,
            segmentation.metadata.fixture or instance.fixture,
        )

    def _result(self, segmentation, arch, teeth, notes):
        ordered = tuple(sorted(teeth, key=lambda tooth: tooth.instance.instance_id))
        return ToothIdentificationResult(
            arch,
            ordered,
            segmentation.metadata.provenance,
            segmentation.metadata.fixture or any(tooth.fixture for tooth in ordered),
            notes,
        )
