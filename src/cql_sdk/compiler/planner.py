"""Expression planner: walks ELM and verifies operator coverage up front."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cql_sdk.elm.models.base import ElmNode

if TYPE_CHECKING:
    from cql_sdk.abstractions.operators import OperatorRegistry
    from cql_sdk.elm.models.library import Library


def missing_operators(library: Library, registry: OperatorRegistry) -> set[str]:
    """Return ELM node types referenced by ``library`` but absent from ``registry``.

    Useful as a fail-fast validation step before attempting execution.
    """
    missing: set[str] = set()
    for definition in library.definitions.values():
        _walk(definition.expression, registry, missing)
    return missing


def _walk(node: ElmNode, registry: OperatorRegistry, missing: set[str]) -> None:
    if node.type and not registry.has(node.type):
        missing.add(node.type)
    for value in node.payload.values():
        _walk_value(value, registry, missing)


def _walk_value(value: object, registry: OperatorRegistry, missing: set[str]) -> None:
    if isinstance(value, dict) and "type" in value:
        _walk(ElmNode.from_json(value), registry, missing)
    elif isinstance(value, list):
        for item in value:
            _walk_value(item, registry, missing)
