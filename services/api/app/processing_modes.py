"""Explicit boundary between real-case and test-fixture processing (WP-01).

REAL_CASE_PROCESSING
  - Uses uploaded STL bytes only
  - Runs ToothInstanceNet (or configured real backend)
  - Never loads fixture geometry
  - Failures stay failures

TEST_FIXTURE_PROCESSING
  - Opt-in only via ALIGNERSTUDIO_ALLOW_TEST_FIXTURE_BACKEND
  - Backend must be toothinstancenet_fixture
  - When a source mesh is provided, its hash must match the verified artifact STL
  - Never used as a silent fallback for real uploads
"""

from __future__ import annotations

import os
from enum import StrEnum


class ProcessingMode(StrEnum):
    REAL_CASE = "real_case"
    TEST_FIXTURE = "test_fixture"


class ProcessingModeError(ValueError):
    """Raised when fixture processing is requested outside the explicit test boundary."""


def selected_backend() -> str:
    return os.environ.get("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "onnx").strip().lower()


def is_test_fixture_backend_allowed() -> bool:
    value = os.environ.get("ALIGNERSTUDIO_ALLOW_TEST_FIXTURE_BACKEND", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def resolve_processing_mode(*, allow_fixture_without_flag: bool = False) -> ProcessingMode:
    """Resolve the active processing mode.

    Fixture mode requires an explicit allow flag unless a caller is a dedicated
    test helper that already sits behind the test boundary.
    """
    backend = selected_backend()
    if backend == "toothinstancenet_fixture":
        if allow_fixture_without_flag or is_test_fixture_backend_allowed():
            return ProcessingMode.TEST_FIXTURE
        raise ProcessingModeError(
            "toothinstancenet_fixture is blocked for production real-case processing. "
            "Set ALIGNERSTUDIO_ALLOW_TEST_FIXTURE_BACKEND=1 only for tests/regression, "
            "or use ALIGNERSTUDIO_SEGMENTATION_BACKEND=toothinstancenet for real uploads."
        )
    return ProcessingMode.REAL_CASE


def require_real_case_mode() -> ProcessingMode:
    """Force the real-case boundary — fixture backends are rejected."""
    backend = selected_backend()
    if backend == "toothinstancenet_fixture":
        raise ProcessingModeError(
            "Real-case processing refuses toothinstancenet_fixture. "
            "Uploaded STL geometry must flow through the genuine ToothInstanceNet path."
        )
    return ProcessingMode.REAL_CASE
