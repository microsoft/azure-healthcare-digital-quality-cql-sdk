"""Packaging seam for emitting library/manifest/resource artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class PackageWriter(Protocol):
    """Writes a logical package (ELM + resources + manifest) to disk."""

    def write(self, *, output_dir: Path, manifest: Any, resources: list[Any]) -> Path:
        """Persist the package and return the root output path."""
