"""TADPM research adapter boundary — Unavailable until offline evidence exists."""

from __future__ import annotations

from dataclasses import dataclass


class TADPMUnavailableError(RuntimeError):
    """Raised when TADPM cannot be used for planning."""

    state = "model_unavailable"


@dataclass(frozen=True)
class TADPMConfig:
    """Configuration gate for TADPM. No checkpoints are bundled."""

    model_name: str = "tadpm"
    model_version: str | None = None
    enabled: bool = False

    def require_available(self) -> None:
        raise TADPMUnavailableError(
            "TADPM is REFERENCE ONLY. No verified checkpoint, license gate, or "
            "Aligner Studio real-case benchmark is available. See "
            "research/benchmark/tadpm/evaluation.json and REUSE_MATRIX.md."
        )


class TADPMAdapter:
    """Adapter boundary for TADPM. Does not load weights or invent arrangements."""

    def __init__(self, config: TADPMConfig | None = None) -> None:
        self.config = config or TADPMConfig()

    def propose_arrangement(self, *_args, **_kwargs):
        self.config.require_available()
