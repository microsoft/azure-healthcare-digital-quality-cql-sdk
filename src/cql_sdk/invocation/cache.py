"""Tiny per-toolkit result cache."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ResultCache:
    """Keyed by ``(library_identifier, definition, params_hash)``."""

    _data: dict[tuple[str, str, int], Any] = field(default_factory=dict)

    def get(self, key: tuple[str, str, int]) -> Any | None:
        return self._data.get(key)

    def has(self, key: tuple[str, str, int]) -> bool:
        return key in self._data

    def set(self, key: tuple[str, str, int], value: Any) -> None:
        self._data[key] = value

    def clear(self) -> None:
        self._data.clear()
