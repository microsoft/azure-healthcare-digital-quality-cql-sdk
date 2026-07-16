"""The :class:`RuntimeContext` that carries evaluation state.

Everything an operator may need is reachable from here:

* the active :class:`~cql_sdk.elm.models.library.Library`
* the operator registry
* parameters
* the execution timestamp ("now")
* optional terminology / data source providers

Contexts are cheap to construct and *intended* to be overridden by FHIR or
Spark layers to plug in specialized data access without changing the core.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from cql_sdk.runtime import operators as _ops

if TYPE_CHECKING:
    from cql_sdk.abstractions.data_source import DataSource
    from cql_sdk.abstractions.terminology import TerminologyProvider
    from cql_sdk.elm.models.base import ElmNode
    from cql_sdk.elm.models.library import Library
    from cql_sdk.invocation.library_registry import LibraryRegistry


@dataclass(slots=True)
class RuntimeContext:
    """Execution state passed to every operator call."""

    library: Library | None = None
    operators: _ops.DefaultOperatorRegistry = field(default_factory=_ops.DefaultOperatorRegistry)
    parameters: dict[str, Any] = field(default_factory=dict)
    now: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    terminology: TerminologyProvider | None = None
    data_source: DataSource | None = None
    subject: Any | None = None
    library_registry: LibraryRegistry | None = None
    _alias_stack: list[dict[str, Any]] = field(default_factory=list, repr=False)
    _let_stack: list[dict[str, Any]] = field(default_factory=list, repr=False)
    _operand_stack: list[dict[str, Any]] = field(default_factory=list, repr=False)
    _cache: dict[str, Any] = field(default_factory=dict, repr=False)

    # --- construction helpers -------------------------------------------

    @classmethod
    def default(cls, **overrides: Any) -> RuntimeContext:
        """Create a context with sensible defaults plus optional overrides."""
        ctx = cls()
        for key, value in overrides.items():
            if not hasattr(ctx, key):
                raise TypeError(f"Unknown RuntimeContext field: {key!r}")
            setattr(ctx, key, value)
        return ctx

    def with_library(self, library: Library) -> RuntimeContext:
        self.library = library
        self._cache.clear()
        return self

    def with_parameters(self, parameters: dict[str, Any] | None) -> RuntimeContext:
        self.parameters = dict(parameters or {})
        self._cache.clear()
        return self

    # --- evaluation -----------------------------------------------------

    def evaluate(self, node: ElmNode) -> Any:
        """Evaluate an ELM node against this context."""
        return _ops.evaluate(self, node)

    def evaluate_definition(self, name: str) -> Any:
        """Evaluate a named library definition, caching the result."""
        if self.library is None:
            raise RuntimeError("RuntimeContext has no library attached.")
        if name in self._cache:
            return self._cache[name]
        definition = self.library.get_definition(name)
        result = self.evaluate(definition.expression)
        self._cache[name] = result
        return result

    # --- alias / let scopes (used by Query, Let, AliasRef, QueryLetRef) ---

    def push_alias_frame(self, frame: dict[str, Any]) -> None:
        self._alias_stack.append(frame)

    def pop_alias_frame(self) -> None:
        self._alias_stack.pop()

    def lookup_alias(self, name: str) -> Any:
        for frame in reversed(self._alias_stack):
            if name in frame:
                return frame[name]
        raise KeyError(f"Alias '{name}' not in scope")

    def push_let_frame(self, frame: dict[str, Any]) -> None:
        self._let_stack.append(frame)

    def pop_let_frame(self) -> None:
        self._let_stack.pop()

    def lookup_let(self, name: str) -> Any:
        for frame in reversed(self._let_stack):
            if name in frame:
                return frame[name]
        raise KeyError(f"Let binding '{name}' not in scope")

    # --- operand (function parameter) scopes -----------------------------

    def push_operand_frame(self, frame: dict[str, Any]) -> None:
        self._operand_stack.append(frame)

    def pop_operand_frame(self) -> None:
        self._operand_stack.pop()

    def lookup_operand(self, name: str) -> Any:
        for frame in reversed(self._operand_stack):
            if name in frame:
                return frame[name]
        raise KeyError(f"Operand '{name}' not in scope")

    # --- cross-library evaluation ----------------------------------------

    def evaluate_in_library(self, library_identifier: str, definition: str) -> Any:
        """Evaluate ``definition`` in a different (already-registered) library."""
        if self.library_registry is None:
            raise RuntimeError(
                "RuntimeContext has no library_registry; cannot resolve cross-library reference "
                f"'{library_identifier}.{definition}'."
            )
        other = self.library_registry.get(library_identifier)
        saved_library = self.library
        saved_cache = self._cache
        try:
            self.library = other
            self._cache = {}
            return self.evaluate_definition(definition)
        finally:
            self.library = saved_library
            self._cache = saved_cache

    # --- user-defined function evaluation --------------------------------

    def evaluate_function(self, name: str, args: list[Any]) -> Any:
        """Evaluate a same-library function, binding ``args`` to its operands.

        Unlike :meth:`evaluate_definition`, function results are never cached
        (they depend on the argument values), and the alias/let scopes are
        isolated so the function body sees only its own operands.
        """
        if self.library is None:
            raise RuntimeError("RuntimeContext has no library attached.")
        definition = self.library.get_definition(name)
        params = getattr(self.library, "function_operands", {}).get(name, [])
        frame = {p: (args[i] if i < len(args) else None) for i, p in enumerate(params)}
        saved_alias, saved_let = self._alias_stack, self._let_stack
        self._alias_stack, self._let_stack = [], []
        self.push_operand_frame(frame)
        try:
            return self.evaluate(definition.expression)
        finally:
            self.pop_operand_frame()
            self._alias_stack, self._let_stack = saved_alias, saved_let

    def evaluate_function_in_library(
        self, library_identifier: str, name: str, args: list[Any]
    ) -> Any:
        """Evaluate a function defined in another registered library."""
        if self.library_registry is None:
            raise RuntimeError(
                "RuntimeContext has no library_registry; cannot resolve cross-library "
                f"function '{library_identifier}.{name}'."
            )
        other = self.library_registry.get(library_identifier)
        saved_library = self.library
        saved_cache = self._cache
        try:
            self.library = other
            self._cache = {}
            return self.evaluate_function(name, args)
        finally:
            self.library = saved_library
            self._cache = saved_cache
