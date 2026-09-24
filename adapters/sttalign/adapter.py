"""STTAlign research adapter boundary — Unavailable until offline evidence exists."""

from __future__ import annotations

from dataclasses import dataclass


class STTAlignUnavailableError(RuntimeError):
    """Raised when STTAlign cannot be used for planning."""

    state = "model_unavailable"


@dataclass(frozen=True)
class STTAlignConfig:
    """Configuration gate for STTAlign. No checkpoints are bundled."""

    model_name: str = "sttalign"
    model_version: str | None = None
    enabled: bool = False

    def require_available(self) -> None:
        raise STTAlignUnavailableError(
            "STTAlign is REFERENCE ONLY. No verified checkpoint, license gate, or "
            "Aligner Studio real-case benchmark is available. See "
            "research/benchmark/sttalign/evaluation.json and REUSE_MATRIX.md."
        )


class STTAlignAdapter:
    """Adapter boundary for STTAlign. Does not load weights or invent proposals."""

    def __init__(self, config: STTAlignConfig | None = None) -> None:
        self.config = config or STTAlignConfig()

    def propose_alignment(self, *_args, **_kwargs):
        self.config.require_available()
