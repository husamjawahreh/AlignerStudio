"""Data provenance tagging shared across domain, engines, and API layers.

Never represent generated/experimental data as clinically reviewed.
"""

from __future__ import annotations

from enum import Enum


class DataProvenance(str, Enum):
    """Tracks how a piece of data came to exist."""

    REAL = "real"
    """Measured/derived directly from the uploaded scan without algorithmic guessing."""

    GENERATED = "generated"
    """Produced by an engine/algorithm; not yet reviewed by a clinician."""

    EXPERIMENTAL = "experimental"
    """Produced by an adapter/model still under evaluation."""

    FIXTURE = "fixture"
    """Deterministic engineering/test data; never a clinical result."""

    CLINICALLY_REVIEWED = "clinically_reviewed"
    """Explicitly approved by a doctor in the review UI."""
