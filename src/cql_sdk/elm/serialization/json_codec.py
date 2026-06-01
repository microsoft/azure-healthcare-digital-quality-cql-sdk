"""JSON codec helpers for ELM.

Kept deliberately thin — centralizing JSON read/write here means the rest of
the SDK never needs to ``import json`` for ELM artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected top-level JSON object at {path}, got {type(data).__name__}")
    return data


def loads(text: str) -> dict[str, Any]:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Expected top-level JSON object")
    return data


def dumps(obj: dict[str, Any], *, pretty: bool = True) -> str:
    return json.dumps(obj, indent=2 if pretty else None, ensure_ascii=False)
