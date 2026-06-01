"""ELM type-name -> Python type management."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class TypeManager:
    """Very small registry mapping ELM type names to Python constructors."""

    mapping: dict[str, type] = field(default_factory=dict)

    def register(self, elm_type: str, py_type: type) -> None:
        self.mapping[elm_type] = py_type

    def resolve(self, elm_type: str) -> type | None:
        return self.mapping.get(elm_type)
