"""Operator registry protocol.

An operator registry maps ELM operator/expression node *type names* to
executable Python callables. Keeping this behind a Protocol lets the runtime,
FHIR, and Spark layers swap or extend operator behavior without touching
core planner/invoker code.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

OperatorFn = Any  # Callable[[RuntimeContext, ElmNode, ...], Any] — kept loose to avoid cycles


@runtime_checkable
class OperatorRegistry(Protocol):
    """Maps ELM node type names to executable operator callables."""

    def register(self, elm_type: str, fn: OperatorFn) -> None:
        """Register (or replace) an operator implementation."""

    def get(self, elm_type: str) -> OperatorFn:
        """Return the operator callable for ``elm_type``.

        Raises:
            KeyError: if no operator is registered for ``elm_type``.
        """

    def has(self, elm_type: str) -> bool:
        """Return whether an operator is registered for ``elm_type``."""
