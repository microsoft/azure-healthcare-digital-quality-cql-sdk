"""ELM library loader.

Reads ``.elm.json`` documents, normalizes their shape, and produces a
:class:`cql_sdk.elm.models.library.Library`. All JSON and compatibility
concerns are kept in this module so runtime code never deals with raw JSON.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cql_sdk.elm.models.base import ElmNode
from cql_sdk.elm.models.library import Library, LibraryDefinition, LibraryIdentifier
from cql_sdk.elm.serialization import compatibility, json_codec


def load_library_from_path(path: Path) -> Library:
    """Load and parse a library from a JSON file on disk."""
    if not path.exists():
        raise FileNotFoundError(f"ELM file not found: {path}")
    payload = json_codec.read_json(path)
    return _build_library(payload)


def load_library_from_string(text: str) -> Library:
    """Load and parse a library from a JSON string."""
    return _build_library(json_codec.loads(text))


def _build_library(raw: dict[str, Any]) -> Library:
    body = compatibility.normalize_library_payload(raw)

    identifier = _extract_identifier(body)
    definitions = {
        d["name"]: LibraryDefinition(
            name=d["name"],
            expression=ElmNode.from_json(d.get("expression", {}) if isinstance(d.get("expression"), dict) else {}),
            access_level=str(d.get("accessLevel", "Public")),
            context=d.get("context"),
        )
        for d in compatibility.iter_statements(body)
        if isinstance(d.get("name"), str)
    }
    parameters = {
        p["name"]: ElmNode.from_json(p)
        for p in compatibility.iter_parameters(body)
        if isinstance(p.get("name"), str)
    }
    function_operands = {
        d["name"]: [
            str(op.get("name"))
            for op in d.get("operand", [])
            if isinstance(op, dict) and isinstance(op.get("name"), str)
        ]
        for d in compatibility.iter_statements(body)
        if isinstance(d.get("name"), str) and isinstance(d.get("operand"), list)
    }
    includes = [
        LibraryIdentifier(id=str(i.get("path", i.get("localIdentifier", ""))), version=i.get("version"))
        for i in compatibility.iter_includes(body)
    ]

    value_sets = _extract_named_defs(body.get("valueSets"))
    code_systems = _extract_named_defs(body.get("codeSystems"))
    codes = _extract_named_defs(body.get("codes"))

    return Library(
        identifier=identifier,
        definitions=definitions,
        parameters=parameters,
        includes=includes,
        value_sets=value_sets,
        code_systems=code_systems,
        codes=codes,
        function_operands=function_operands,
        raw=raw,
    )


def _extract_identifier(body: dict[str, Any]) -> LibraryIdentifier:
    ident = body.get("identifier", {})
    if not isinstance(ident, dict):
        ident = {}
    return LibraryIdentifier(
        id=str(ident.get("id", "UnnamedLibrary")),
        version=ident.get("version"),
    )


def _extract_named_defs(container: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(container, dict):
        return {}
    defs = container.get("def", [])
    if not isinstance(defs, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for item in defs:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            out[item["name"]] = item
    return out
