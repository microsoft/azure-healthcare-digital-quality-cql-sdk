"""The :class:`InvocationToolkit` — preferred public entry point.

Responsibilities:

* Register one or more loaded libraries.
* Build default runtime contexts (or accept user-supplied ones).
* Validate operator coverage before execution.
* Invoke named definitions and cache results.
* Hide internal details such as operator registries, planners, and
  serializer compatibility handling.
"""

from __future__ import annotations

from typing import Any

from cql_sdk.compiler.planner import missing_operators
from cql_sdk.elm.models.library import Library, LibraryIdentifier
from cql_sdk.invocation.cache import ResultCache
from cql_sdk.invocation.invoker import Invoker
from cql_sdk.invocation.library_registry import LibraryRegistry
from cql_sdk.runtime.context import RuntimeContext


class InvocationToolkit:
    """High-level facade for loading + invoking ELM libraries."""

    def __init__(self, *, auto_register_fhir_helpers: bool = True) -> None:
        self._registry = LibraryRegistry()
        self._invoker = Invoker()
        self._cache = ResultCache()
        if auto_register_fhir_helpers:
            self._register_synthetic_fhir_helpers()

    # --- Registration ---------------------------------------------------

    def register(self, library: Library) -> None:
        """Register a loaded library with the toolkit."""
        self._registry.register(library)

    def has(self, identifier: str | LibraryIdentifier) -> bool:
        return self._registry.has(identifier)

    def _register_synthetic_fhir_helpers(self) -> None:
        # Lazy import to avoid a hard dependency cycle.
        from cql_sdk.fhir.helpers import synthetic_fhir_helpers

        if not self._registry.has("FHIRHelpers"):
            self._registry.register(synthetic_fhir_helpers())

    # --- Validation -----------------------------------------------------

    def validate(self, identifier: str | LibraryIdentifier) -> set[str]:
        """Return the set of ELM node types in the library with no operator.

        An empty set means the library is executable with the built-in
        operator registry.
        """
        library = self._registry.get(identifier)
        ctx = RuntimeContext.default()
        return missing_operators(library, ctx.operators)

    # --- Invocation -----------------------------------------------------

    def invoke(
        self,
        *,
        library_identifier: str | LibraryIdentifier,
        definition: str,
        parameters: dict[str, Any] | None = None,
        context: RuntimeContext | None = None,
    ) -> Any:
        """Evaluate ``definition`` on the named library."""
        library = self._registry.get(library_identifier)
        cache_key = (str(library.identifier), definition, _hash_params(parameters))
        if self._cache.has(cache_key):
            return self._cache.get(cache_key)

        ctx = context or RuntimeContext.default()
        ctx.library_registry = self._registry
        result = self._invoker.invoke(
            library=library,
            definition=definition,
            context=ctx,
            parameters=parameters,
        )
        self._cache.set(cache_key, result)
        return result

    def clear_cache(self) -> None:
        self._cache.clear()


def _hash_params(parameters: dict[str, Any] | None) -> int:
    if not parameters:
        return 0
    try:
        return hash(tuple(sorted(parameters.items())))
    except TypeError:
        # Fall back to repr for unhashable values (lists, dicts, …).
        return hash(repr(sorted(parameters.items())))
