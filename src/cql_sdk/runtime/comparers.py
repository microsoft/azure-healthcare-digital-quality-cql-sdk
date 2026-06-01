"""CQL three-valued comparers.

CQL comparisons can return ``null`` (unknown). These helpers make that
explicit so the runtime never accidentally collapses to Python truthiness.

The equality / equivalence helpers also handle the CQL value types that
need bespoke semantics — ``Quantity`` (same unit, value equal) and FHIR
``Coding`` / ``CodeableConcept`` dicts (``~`` operator).
"""

from __future__ import annotations

from typing import Any

from cql_sdk.abstractions.terminology import Code
from cql_sdk.runtime.quantities import Quantity


def equal(a: Any, b: Any) -> bool | None:
    if a is None or b is None:
        return None
    if isinstance(a, Quantity) and isinstance(b, Quantity):
        if a.unit != b.unit:
            return False
        return bool(a.value == b.value)
    return bool(a == b)


def less(a: Any, b: Any) -> bool | None:
    if a is None or b is None:
        return None
    if isinstance(a, Quantity) and isinstance(b, Quantity):
        if a.unit != b.unit:
            return None
        return bool(a.value < b.value)
    try:
        return bool(a < b)
    except TypeError:
        return None


def greater(a: Any, b: Any) -> bool | None:
    if a is None or b is None:
        return None
    if isinstance(a, Quantity) and isinstance(b, Quantity):
        if a.unit != b.unit:
            return None
        return bool(a.value > b.value)
    try:
        return bool(a > b)
    except TypeError:
        return None


def equivalent(a: Any, b: Any) -> bool | None:
    """CQL ``~`` operator. Equivalence is intentionally lenient.

    * Codes / Codings are equivalent if their ``code`` (and ``system`` when
      both present) match.
    * CodeableConcepts are equivalent if any of their codings is equivalent
      to any of the other side's codings (or any of the other side itself
      when it's a Code/Coding).
    * A Coding compared to a plain string matches when the string equals
      the coding's ``code`` or ``display``.
    * Everything else falls back to ``equal``.
    """
    if a is None or b is None:
        return None

    a_codes = _to_codings(a)
    b_codes = _to_codings(b)
    if a_codes is not None and b_codes is not None:
        return any(_codings_equivalent(x, y) for x in a_codes for y in b_codes)
    if a_codes is not None and isinstance(b, str):
        return any(_coding_matches_string(c, b) for c in a_codes)
    if b_codes is not None and isinstance(a, str):
        return any(_coding_matches_string(c, a) for c in b_codes)
    return equal(a, b)


def _coding_matches_string(coding: dict[str, Any], s: str) -> bool:
    if coding.get("code") == s:
        return True
    display = coding.get("display")
    return isinstance(display, str) and s.lower() in display.lower()


def _to_codings(value: Any) -> list[dict[str, Any]] | None:
    if isinstance(value, Code):
        return [{"code": value.code, "system": value.system}]
    if isinstance(value, dict):
        coding = value.get("coding")
        if isinstance(coding, list):
            return [c for c in coding if isinstance(c, dict)]
        if "code" in value:
            return [value]
    return None


def _codings_equivalent(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if a.get("code") != b.get("code"):
        return False
    sys_a, sys_b = a.get("system"), b.get("system")
    if sys_a is None or sys_b is None:
        return True
    return bool(sys_a == sys_b)
