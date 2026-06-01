"""Library registry: maps identifier -> loaded :class:`Library`."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from cql_sdk.elm.models.library import Library, LibraryIdentifier


@dataclass(slots=True)
class LibraryRegistry:
    """Small in-memory registry keyed by ``"id"`` or ``"id|version"``."""

    _libraries: dict[str, Library] = field(default_factory=dict)

    def register(self, library: Library) -> None:
        self._libraries[str(library.identifier)] = library
        self._libraries.setdefault(library.identifier.id, library)

    def get(self, identifier: str | LibraryIdentifier) -> Library:
        key = str(identifier)
        try:
            return self._libraries[key]
        except KeyError as exc:
            raise KeyError(f"Library '{key}' is not registered.") from exc

    def has(self, identifier: str | LibraryIdentifier) -> bool:
        return str(identifier) in self._libraries

    def __iter__(self) -> Iterator[Library]:
        # De-duplicate since we register twice (id and id|version).
        seen: set[int] = set()
        for lib in self._libraries.values():
            if id(lib) in seen:
                continue
            seen.add(id(lib))
            yield lib
