"""Tooth domain entity using FDI (ISO 3950) numbering."""

from __future__ import annotations

from dataclasses import dataclass

FDI_TOOTH_NUMBERS: frozenset[int] = frozenset(
    [*range(11, 19), *range(21, 29), *range(31, 39), *range(41, 49)]
)


def is_valid_fdi_number(number: int) -> bool:
    """Whether ``number`` is a valid FDI permanent-tooth designation."""
    return number in FDI_TOOTH_NUMBERS


@dataclass(frozen=True)
class Tooth:
    """A single tooth identified within a case, using FDI numbering."""

    fdi_number: int

    def __post_init__(self) -> None:
        if not is_valid_fdi_number(self.fdi_number):
            raise ValueError(f"Invalid FDI tooth number: {self.fdi_number}")

    @property
    def quadrant(self) -> int:
        return self.fdi_number // 10

    @property
    def arch(self) -> str:
        return "upper" if self.quadrant in (1, 2) else "lower"
