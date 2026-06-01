"""ELM :class:`Library` model — the top-level artifact produced by CQL-to-ELM."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cql_sdk.elm.models.base import ElmNode


@dataclass(slots=True)
class LibraryIdentifier:
    id: str
    version: str | None = None

    def __str__(self) -> str:
        return f"{self.id}" + (f"|{self.version}" if self.version else "")


@dataclass(slots=True)
class LibraryDefinition:
    """A single named `def` or `function` inside a library."""

    name: str
    expression: ElmNode
    access_level: str = "Public"
    context: str | None = None


@dataclass(slots=True)
class Library:
    """An ELM library: the loaded, parsed form of a ``.elm.json`` file."""

    identifier: LibraryIdentifier
    definitions: dict[str, LibraryDefinition] = field(default_factory=dict)
    parameters: dict[str, ElmNode] = field(default_factory=dict)
    includes: list[LibraryIdentifier] = field(default_factory=list)
    value_sets: dict[str, dict[str, Any]] = field(default_factory=dict)
    code_systems: dict[str, dict[str, Any]] = field(default_factory=dict)
    codes: dict[str, dict[str, Any]] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    """The original parsed JSON, preserved for pass-through scenarios."""

    def has_definition(self, name: str) -> bool:
        return name in self.definitions

    def get_definition(self, name: str) -> LibraryDefinition:
        try:
            return self.definitions[name]
        except KeyError as exc:
            raise KeyError(
                f"Definition '{name}' not found in library '{self.identifier}'."
            ) from exc
