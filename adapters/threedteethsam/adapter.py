"""3DTeethSAM research adapter boundary — segmentation candidate, not a planner."""

from __future__ import annotations

from dataclasses import dataclass


class TeethSAMUnavailableError(RuntimeError):
    """Raised when 3DTeethSAM cannot be used."""

    state = "model_unavailable"


@dataclass(frozen=True)
class TeethSAMConfig:
    """Configuration gate for 3DTeethSAM. No checkpoints are bundled."""

    model_name: str = "3dteethsam"
    model_version: str | None = None
    enabled: bool = False

    def require_available(self) -> None:
        raise TeethSAMUnavailableError(
            "3DTeethSAM is a segmentation BENCHMARK CANDIDATE, not a planning engine. "
            "No Aligner Studio benchmark run has cleared it for production use, and it "
            "must not replace ToothInstanceNet without measured evidence. See "
            "research/benchmark/3dteethsam/evaluation.json and REUSE_MATRIX.md."
        )


class TeethSAMAdapter:
    """Adapter boundary for 3DTeethSAM. Planning callers always get Unavailable."""

    def __init__(self, config: TeethSAMConfig | None = None) -> None:
        self.config = config or TeethSAMConfig()

    def segment(self, *_args, **_kwargs):
        self.config.require_available()

    def propose_plan(self, *_args, **_kwargs):
        """3DTeethSAM is not a planning model — always unavailable."""
        self.config.require_available()
