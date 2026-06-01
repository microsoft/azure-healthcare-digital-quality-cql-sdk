"""ELM type-reference helpers (NamedTypeSpecifier, ListTypeSpecifier, …)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TypeRef:
    """Lightweight reference to an ELM type (e.g. ``System.Integer``)."""

    name: str
    namespace: str | None = None

    @property
    def qualified(self) -> str:
        return f"{self.namespace}.{self.name}" if self.namespace else self.name
