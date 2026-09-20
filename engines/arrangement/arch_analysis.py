"""Initial descriptive arch analysis."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from domain.tooth.arch import ArchCenterlinePoint, ArchMeasurements
from domain.tooth.identification import ArchType, ToothIdentificationResult
from engines.arrangement.geometry import ToothGeometryError, build_arch_axes


class ArchAnalysisError(ValueError):
    """Raised when identified geometry is insufficient for arch measurements."""


@dataclass(frozen=True)
class ArchAnalysisEngine:
    """Computes descriptive spatial relationships without clinical interpretation."""

    def analyze(self, identification: ToothIdentificationResult) -> ArchMeasurements:
        teeth = list(identification.identified)
        if len(teeth) < 2:
            raise ArchAnalysisError("At least two identified teeth are required")
        centroids = np.asarray([tooth.landmarks.centroid for tooth in teeth], dtype=np.float64)
        try:
            axes = build_arch_axes(centroids)
        except ToothGeometryError as exc:
            raise ArchAnalysisError(str(exc)) from exc
        projected = [
            (
                tooth,
                float(
                    np.dot(np.asarray(tooth.landmarks.centroid) - centroids.mean(axis=0), axes[0])
                ),
            )
            for tooth in teeth
        ]
        ordered = sorted(projected, key=lambda item: item[1])
        lateral_values = [value for _, value in ordered]
        total_width = lateral_values[-1] - lateral_values[0]
        left_half = max((value for _, value in projected), default=0.0)
        right_half = abs(min((value for _, value in projected), default=0.0))
        consecutive = tuple(
            float(
                np.linalg.norm(
                    np.asarray(first.landmarks.centroid) - np.asarray(second.landmarks.centroid)
                )
            )
            for (first, _), (second, _) in zip(ordered, ordered[1:], strict=False)
        )
        identity_by_number = {tooth.identity.number: tooth for tooth in teeth if tooth.identity}
        if identification.arch is ArchType.UPPER:
            anterior_numbers, posterior_numbers = (11, 21), (18, 28)
        else:
            anterior_numbers, posterior_numbers = (41, 31), (48, 38)
        anterior_width = self._distance(identity_by_number, anterior_numbers)
        posterior_width = self._distance(identity_by_number, posterior_numbers)
        anterior_order = tuple(
            tooth.instance.instance_id
            for tooth, _ in sorted(projected, key=lambda item: abs(item[1]))
        )
        centerline = tuple(
            ArchCenterlinePoint(tooth.instance.instance_id, tooth.landmarks.centroid)
            for tooth, _ in ordered
        )
        return ArchMeasurements(
            arch=identification.arch,
            centerline=centerline,
            ordered_instance_ids=tuple(tooth.instance.instance_id for tooth, _ in ordered),
            total_width=float(total_width),
            left_half_width=float(left_half),
            right_half_width=float(right_half),
            anterior_width=anterior_width,
            posterior_width=posterior_width,
            consecutive_tooth_distances=consecutive,
            anterior_to_posterior_order=anterior_order,
            provenance=identification.provenance,
            fixture=identification.fixture,
            notes="Descriptive geometry only; no diagnosis or clinical threshold is applied.",
        )

    @staticmethod
    def _distance(teeth, numbers: tuple[int, int]) -> float | None:
        if any(number not in teeth for number in numbers):
            return None
        first = np.asarray(teeth[numbers[0]].landmarks.centroid)
        second = np.asarray(teeth[numbers[1]].landmarks.centroid)
        return float(np.linalg.norm(first - second))
