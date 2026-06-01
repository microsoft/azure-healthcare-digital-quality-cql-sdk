"""Helpers for resolving library definitions during evaluation."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cql_sdk.elm.models.library import Library, LibraryDefinition


def resolve_definition(library: Library, name: str) -> LibraryDefinition:
    """Return the :class:`LibraryDefinition` for ``name`` or raise ``KeyError``."""
    return library.get_definition(name)
