"""CQL ``Quantity`` value."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Quantity:
    value: Decimal
    unit: str

    def __str__(self) -> str:
        return f"{self.value} {self.unit}"
