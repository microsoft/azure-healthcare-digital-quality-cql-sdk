"""Low-level invoker used by :class:`InvocationToolkit`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cql_sdk.elm.models.library import Library
    from cql_sdk.runtime.context import RuntimeContext


class Invoker:
    """Evaluate a named definition from a library against a runtime context."""

    def invoke(
        self,
        *,
        library: Library,
        definition: str,
        context: RuntimeContext,
        parameters: dict[str, Any] | None = None,
    ) -> Any:
        context.with_library(library).with_parameters(parameters)
        return context.evaluate_definition(definition)
