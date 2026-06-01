"""FHIR terminology provider implementations.

* :class:`InMemoryTerminology` — minimal map keyed by value-set id.
* :class:`StaticTerminologyProvider` — loads FHIR R4 ``ValueSet`` resources
  from a directory on disk (one JSON file per value set or a Bundle of
  value sets). Resolves both by canonical URL and by id.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cql_sdk.abstractions.terminology import Code, ValueSetRef


class InMemoryTerminology:
    """Tiny in-memory terminology provider for tests and examples."""

    def __init__(self, value_sets: dict[str, list[Code]] | None = None) -> None:
        self._vs = value_sets or {}

    def expand(self, value_set: ValueSetRef) -> list[Code]:
        return list(self._vs.get(value_set.id, []))

    def in_value_set(self, code: Code, value_set: ValueSetRef) -> bool:
        return any(_codes_match(code, c) for c in self._vs.get(value_set.id, []))


class StaticTerminologyProvider:
    """Loads ``ValueSet`` resources from a directory.

    Supports two file layouts:

    1. One ``ValueSet`` JSON resource per file (preferred for VSAC snapshots).
    2. A FHIR Bundle whose entries are ``ValueSet`` resources.

    Value sets are indexed by both ``url`` and ``id`` so lookups work
    regardless of which form a measure references.
    """

    def __init__(self, value_sets_dir: str | Path | None = None) -> None:
        self._by_url: dict[str, list[Code]] = {}
        self._by_id: dict[str, list[Code]] = {}
        if value_sets_dir is not None:
            self.load_directory(value_sets_dir)

    def load_directory(self, path: str | Path) -> None:
        root = Path(path)
        if not root.exists():
            return
        for file in sorted(root.glob("*.json")):
            try:
                payload = json.loads(file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            self._ingest(payload)

    def _ingest(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            return
        rtype = payload.get("resourceType")
        if rtype == "Bundle":
            for entry in payload.get("entry", []) or []:
                resource = entry.get("resource") if isinstance(entry, dict) else None
                if isinstance(resource, dict):
                    self._ingest(resource)
            return
        if rtype != "ValueSet":
            return
        codes = _extract_codes(payload)
        url = payload.get("url")
        vs_id = payload.get("id")
        if isinstance(url, str):
            self._by_url[url] = codes
        if isinstance(vs_id, str):
            self._by_id[vs_id] = codes

    def expand(self, value_set: ValueSetRef) -> list[Code]:
        return list(self._lookup(value_set))

    def in_value_set(self, code: Code, value_set: ValueSetRef) -> bool:
        return any(_codes_match(code, c) for c in self._lookup(value_set))

    def _lookup(self, value_set: ValueSetRef) -> list[Code]:
        if value_set.id in self._by_url:
            return self._by_url[value_set.id]
        if value_set.id in self._by_id:
            return self._by_id[value_set.id]
        return []


def _extract_codes(value_set: dict[str, Any]) -> list[Code]:
    out: list[Code] = []
    expansion = value_set.get("expansion") or {}
    for c in expansion.get("contains", []) or []:
        if isinstance(c, dict) and "code" in c:
            out.append(
                Code(
                    code=str(c["code"]),
                    system=c.get("system"),
                    display=c.get("display"),
                    version=c.get("version"),
                )
            )
    # Some value sets only have `compose.include[].concept[]`
    compose = value_set.get("compose") or {}
    for inc in compose.get("include", []) or []:
        if not isinstance(inc, dict):
            continue
        system = inc.get("system")
        for concept in inc.get("concept", []) or []:
            if isinstance(concept, dict) and "code" in concept:
                out.append(
                    Code(
                        code=str(concept["code"]),
                        system=system,
                        display=concept.get("display"),
                    )
                )
    return out


def _codes_match(a: Code, b: Code) -> bool:
    if a.code != b.code:
        return False
    if a.system is None or b.system is None:
        return True
    return a.system == b.system
