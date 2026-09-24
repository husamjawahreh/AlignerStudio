"""Public exports for the 3DTeethSAM research adapter boundary."""

from adapters.threedteethsam.adapter import (
    TeethSAMAdapter,
    TeethSAMConfig,
    TeethSAMUnavailableError,
)

__all__ = ["TeethSAMAdapter", "TeethSAMConfig", "TeethSAMUnavailableError"]
