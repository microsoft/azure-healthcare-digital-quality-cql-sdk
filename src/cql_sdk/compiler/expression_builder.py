"""Placeholder for an expression builder that compiles ELM into Python callables."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cql_sdk.elm.models.base import ElmNode
    from cql_sdk.runtime.context import RuntimeContext


def build(expression: ElmNode) -> Callable[[RuntimeContext], Any]:
    """Return a callable that evaluates ``expression`` against a context.

    The current implementation simply wraps :meth:`RuntimeContext.evaluate`;
    a future version may inline/specialize expression trees here.
    """

    def _run(ctx: RuntimeContext) -> Any:
        return ctx.evaluate(expression)

    return _run
