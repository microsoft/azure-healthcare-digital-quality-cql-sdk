"""Typed helpers around common ELM expression shapes."""

from __future__ import annotations

from cql_sdk.elm.models.base import ElmNode


def is_literal(node: ElmNode) -> bool:
    return node.type == "Literal"


def literal_value(node: ElmNode) -> str | None:
    value = node.get("value")
    return None if value is None else str(value)


def literal_value_type(node: ElmNode) -> str | None:
    value_type = node.get("valueType")
    return None if value_type is None else str(value_type)
