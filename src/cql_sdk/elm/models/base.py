"""Common base types for ELM model classes.

The scaffold intentionally uses a loose representation: every ELM expression
is captured as an :class:`ElmNode` holding its discriminator ``type`` plus
the raw payload. This preserves fidelity with the JSON representation and
lets the planner grow rich, typed models over time without requiring a full
schema port up front.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ElmNode:
    """A raw ELM expression node.

    Attributes:
        type: The ELM discriminator (e.g. ``"Literal"``, ``"FunctionRef"``).
        payload: The full JSON object for this node, as produced by the
            CQL-to-ELM translator.
    """

    type: str
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_json(cls, obj: dict[str, Any]) -> ElmNode:
        # ELM JSON uses "type" to encode the node discriminator.
        return cls(type=str(obj.get("type", "")), payload=obj)

    def get(self, key: str, default: Any = None) -> Any:
        return self.payload.get(key, default)
