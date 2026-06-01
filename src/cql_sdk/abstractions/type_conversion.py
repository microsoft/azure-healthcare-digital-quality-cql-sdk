"""Type conversion seam between ELM/CQL types and host Python values."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class TypeConverter(Protocol):
    """Bidirectional conversion between CQL/ELM values and Python values."""

    def to_python(self, cql_value: Any, *, cql_type: str | None = None) -> Any:
        """Convert a CQL/ELM value to an idiomatic Python value."""

    def to_cql(self, py_value: Any, *, cql_type: str | None = None) -> Any:
        """Convert a Python value into the representation expected by ELM."""
