"""CQL ``Interval`` value (half-open or inclusive closed intervals)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Interval:
    low: Any
    high: Any
    low_closed: bool = True
    high_closed: bool = True

    def contains(self, point: Any) -> bool:
        lo_ok = point > self.low or (self.low_closed and point == self.low)
        hi_ok = point < self.high or (self.high_closed and point == self.high)
        return bool(lo_ok and hi_ok)
