"""Package manifest model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PackageManifest:
    name: str
    version: str = "0.0.0"
    libraries: list[str] = field(default_factory=list)
    resources: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "libraries": list(self.libraries),
            "resources": list(self.resources),
            "metadata": dict(self.metadata),
        }
