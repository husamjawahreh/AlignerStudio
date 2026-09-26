"""Evidence-based remaining-time estimates (Wave 8).

Progress is never derived here. A percent still has to come from the job
itself. An estimate is a duration comparison against earlier completions of
the same operation, on this computer, for the same input class.

No samples, a different computer, or a run already outside the observed
range produces no estimate. One or two samples are coarse. Three or more
are measured only when the spread is tight enough to say so.
"""

from __future__ import annotations

import os
import platform
from statistics import median
from typing import Iterable, Mapping, Sequence

NO_RELIABLE_REMAINING_TIME = "No reliable remaining-time estimate"
MEASURED_SAMPLE_COUNT = 3
MAX_MATCHING_SAMPLES = 12
# A run longer than this multiple of the longest observed completion is
# outside the evidence. Do not show a remaining time of zero.
OUT_OF_RANGE_FACTOR = 1.25
# Relative spread (max-min)/median above this stays coarse even with 3+ samples.
MEASURED_SPREAD_LIMIT = 0.75
TIGHT_SPREAD = 0.35
# A band narrower than this is not shown as a range.
RANGE_BAND_SECONDS = 30


def environment_id() -> str:
    """Fingerprint of this computer. Not a patient identifier."""
    return f"{platform.system().lower()}-{platform.machine().lower()}-cpu{os.cpu_count() or 0}"


def duration_class(seconds: float) -> str:
    if seconds < 2:
        return "fast"
    if seconds < 30:
        return "medium"
    if seconds < 180:
        return "long"
    return "very_long"


def _percentile(sorted_values: Sequence[float], fraction: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    index = (len(sorted_values) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = index - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def _about(seconds: int) -> str:
    if seconds < 90:
        return f"About {seconds} seconds remaining"
    minutes = max(1, round(seconds / 60))
    unit = "minute" if minutes == 1 else "minutes"
    return f"About {minutes} {unit} remaining"


def _none(operation_id: str, environment_id_value: str, input_class: str, sample_count: int = 0) -> dict:
    return {
        "kind": "none",
        "seconds": None,
        "low_seconds": None,
        "high_seconds": None,
        "confidence": None,
        "sample_count": sample_count,
        "qualifier": "none",
        "operation_id": operation_id,
        "environment_id": environment_id_value,
        "input_class": input_class,
        "label": NO_RELIABLE_REMAINING_TIME,
        "duration_class": None,
    }


def _sample_field(sample: Mapping[str, object] | object, name: str) -> object:
    if isinstance(sample, Mapping):
        return sample.get(name)
    return getattr(sample, name)


def estimate_remaining(
    samples: Iterable[Mapping[str, object] | object],
    *,
    elapsed_seconds: float | None,
    operation_id: str,
    environment_id: str,
    input_class: str,
) -> dict:
    """Return a remaining-time payload. Never a progress percent."""
    matched: list[float] = []
    for sample in samples:
        if _sample_field(sample, "operation_id") != operation_id:
            continue
        if _sample_field(sample, "environment_id") != environment_id:
            continue
        if _sample_field(sample, "input_class") != input_class:
            continue
        duration = _sample_field(sample, "duration_seconds")
        if isinstance(duration, bool) or not isinstance(duration, (int, float)):
            continue
        if duration <= 0:
            continue
        matched.append(float(duration))
    matched = matched[-MAX_MATCHING_SAMPLES:]
    if not matched or elapsed_seconds is None or elapsed_seconds < 0:
        return _none(operation_id, environment_id, input_class, len(matched))

    observed_max = max(matched)
    if elapsed_seconds > observed_max * OUT_OF_RANGE_FACTOR:
        return _none(operation_id, environment_id, input_class, len(matched))

    center = float(median(matched))
    remaining = center - float(elapsed_seconds)
    if remaining < 1:
        return _none(operation_id, environment_id, input_class, len(matched))

    seconds = int(round(remaining))
    if seconds < 1:
        return _none(operation_id, environment_id, input_class, len(matched))

    spread = (observed_max - min(matched)) / center if center else 1.0
    measured = len(matched) >= MEASURED_SAMPLE_COUNT and spread <= MEASURED_SPREAD_LIMIT
    kind = "measured" if measured else "coarse"
    if measured and spread <= TIGHT_SPREAD:
        confidence = 0.7
    elif measured:
        confidence = 0.55
    elif len(matched) >= 2:
        confidence = 0.4
    else:
        confidence = 0.3

    sorted_values = sorted(matched)
    low = int(round(max(0.0, _percentile(sorted_values, 0.25) - float(elapsed_seconds))))
    high = int(round(max(0.0, _percentile(sorted_values, 0.75) - float(elapsed_seconds))))
    if kind == "measured" and high - low >= RANGE_BAND_SECONDS and low >= 1:
        low_text = _about(low).removeprefix("About ").removesuffix(" remaining")
        high_text = _about(high).removeprefix("About ")
        label = f"Estimated {low_text} to {high_text}. Not a guarantee."
    elif kind == "measured":
        label = f"{_about(seconds)}, estimated. Not a guarantee."
    else:
        label = f"{_about(seconds)}, estimated. Uncertainty is high."

    return {
        "kind": kind,
        "seconds": seconds,
        "low_seconds": low if kind == "measured" else None,
        "high_seconds": high if kind == "measured" else None,
        "confidence": confidence,
        "sample_count": len(matched),
        "qualifier": "estimated",
        "operation_id": operation_id,
        "environment_id": environment_id,
        "input_class": input_class,
        "label": label,
        "duration_class": duration_class(center),
    }
