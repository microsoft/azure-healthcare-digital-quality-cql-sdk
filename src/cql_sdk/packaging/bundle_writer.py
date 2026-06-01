"""Minimal FHIR Bundle writer for packaged resource output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_bundle(resources: list[dict[str, Any]], path: Path) -> None:
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": r} for r in resources],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
