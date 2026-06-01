"""Compatibility shims for variant / legacy ELM JSON representations.

Different CQL-to-ELM translator versions emit slightly different shapes.
Normalize them here so the rest of the SDK sees a single stable layout.
"""

from __future__ import annotations

from typing import Any


def normalize_library_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return ``payload`` unwrapped from a top-level ``library`` envelope.

    The ELM/JSON emitter often wraps the library as ``{"library": {...}}``;
    internally we prefer to work directly with the inner object.
    """
    if "library" in payload and isinstance(payload["library"], dict):
        return payload["library"]
    return payload


def iter_statements(library_obj: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the list of statement defs regardless of legacy nesting."""
    stmts = library_obj.get("statements", {})
    defs = stmts.get("def", []) if isinstance(stmts, dict) else []
    if isinstance(defs, list):
        return [d for d in defs if isinstance(d, dict)]
    return []


def iter_parameters(library_obj: dict[str, Any]) -> list[dict[str, Any]]:
    params = library_obj.get("parameters", {})
    items = params.get("def", []) if isinstance(params, dict) else []
    if isinstance(items, list):
        return [p for p in items if isinstance(p, dict)]
    return []


def iter_includes(library_obj: dict[str, Any]) -> list[dict[str, Any]]:
    inc = library_obj.get("includes", {})
    items = inc.get("def", []) if isinstance(inc, dict) else []
    if isinstance(items, list):
        return [i for i in items if isinstance(i, dict)]
    return []
