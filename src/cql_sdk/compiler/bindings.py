"""Bindings between ELM nodes and operator callables (future expansion)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Binding:
    """Pairs an ELM node type name with a compiled callable."""

    elm_type: str
    callable_: Callable[..., object]
