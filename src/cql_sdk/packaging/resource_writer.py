"""Writes arbitrary resource documents (JSON) to disk."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_resource(resource: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(resource, indent=2), encoding="utf-8")
