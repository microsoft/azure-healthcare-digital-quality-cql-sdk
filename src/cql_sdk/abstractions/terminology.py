"""Terminology provider protocol (value sets, code systems, concepts)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class Code:
    code: str
    system: str | None = None
    display: str | None = None
    version: str | None = None


@dataclass(frozen=True, slots=True)
class ValueSetRef:
    id: str
    version: str | None = None


@runtime_checkable
class TerminologyProvider(Protocol):
    """Resolves value set membership and code system lookups."""

    def expand(self, value_set: ValueSetRef) -> list[Code]:
        """Return the expansion (list of codes) for a value set."""

    def in_value_set(self, code: Code, value_set: ValueSetRef) -> bool:
        """Return whether ``code`` is a member of ``value_set``."""
