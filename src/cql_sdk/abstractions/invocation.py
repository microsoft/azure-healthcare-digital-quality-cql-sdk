"""Invocation protocol — the top-level user-facing seam."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Invoker(Protocol):
    """Executes a named definition on a registered library."""

    def invoke(
        self,
        *,
        library_identifier: str,
        definition: str,
        parameters: dict[str, Any] | None = None,
        context: Any | None = None,
    ) -> Any:
        """Evaluate ``definition`` in the given library and return its value."""
