"""FHIR Bundle-backed :class:`DataSource`."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from cql_sdk.abstractions.terminology import Code, ValueSetRef


@dataclass(slots=True)
class BundleDataSource:
    """Minimal retrieve implementation over an in-memory FHIR bundle.

    Indexes resources by ``resourceType`` on construction and supports
    code-based filtering against a terminology provider (resolved from the
    runtime context) at retrieve time.
    """

    bundle: dict[str, Any]
    _by_type: dict[str, list[dict[str, Any]]] = field(default_factory=dict, init=False, repr=False)
    subject: dict[str, Any] | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        for entry in self.bundle.get("entry", []) or []:
            resource = entry.get("resource") if isinstance(entry, dict) else None
            if isinstance(resource, dict):
                rtype = str(resource.get("resourceType", ""))
                self._by_type.setdefault(rtype, []).append(resource)
        patients = self._by_type.get("Patient")
        if patients:
            self.subject = patients[0]

    def retrieve(
        self,
        *,
        data_type: str,
        code_property: str | None = None,
        codes: Iterable[Any] | None = None,
        date_property: str | None = None,
        date_range: Any | None = None,
        context: Any | None = None,
    ) -> Iterable[dict[str, Any]]:
        rows = self._by_type.get(data_type, [])
        if codes is None:
            return list(rows)

        terminology = getattr(context, "terminology", None) if context is not None else None
        accepted = _expand_filter(codes, terminology)
        if accepted is None:
            return list(rows)

        prop = code_property or _default_code_property(data_type)
        if not prop:
            return list(rows)

        return [r for r in rows if _resource_matches(r, prop, accepted)]


def _expand_filter(codes: Any, terminology: Any) -> set[tuple[str | None, str]] | None:
    if codes is None:
        return None
    accepted: set[tuple[str | None, str]] = set()

    def _add(item: Any) -> None:
        if item is None:
            return
        if isinstance(item, Code):
            accepted.add((item.system, item.code))
            return
        if isinstance(item, dict):
            if "code" in item and not isinstance(item.get("code"), dict):
                accepted.add((item.get("system"), str(item["code"])))
            for c in item.get("coding") or []:
                if isinstance(c, dict) and "code" in c:
                    accepted.add((c.get("system"), str(c["code"])))

    if isinstance(codes, ValueSetRef):
        if terminology is None:
            return None
        for c in terminology.expand(codes):
            _add(c)
        return accepted

    if isinstance(codes, list):
        for c in codes:
            _add(c)
        return accepted

    _add(codes)
    return accepted if accepted else None


def _default_code_property(data_type: str) -> str | None:
    return _DEFAULT_CODE_PROPERTIES.get(data_type)


_DEFAULT_CODE_PROPERTIES: dict[str, str] = {
    "Condition": "code",
    "Observation": "code",
    "Encounter": "type",
    "Procedure": "code",
    "MedicationRequest": "medication",
    "MedicationAdministration": "medication",
    "Immunization": "vaccineCode",
    "AllergyIntolerance": "code",
    "DiagnosticReport": "code",
    "FamilyMemberHistory": "condition",
}


def _resource_matches(
    resource: dict[str, Any],
    code_property: str,
    accepted: set[tuple[str | None, str]],
) -> bool:
    value = resource.get(code_property)
    if value is None:
        for suffix in ("CodeableConcept", "Reference", "Coding"):
            value = resource.get(code_property + suffix)
            if value is not None:
                break
    if value is None:
        return False
    return _value_matches(value, accepted)


def _value_matches(value: Any, accepted: set[tuple[str | None, str]]) -> bool:
    if isinstance(value, list):
        return any(_value_matches(v, accepted) for v in value)
    if not isinstance(value, dict):
        return False
    if "code" in value and not isinstance(value.get("code"), dict) and _matches_pair(
        value.get("system"), value.get("code"), accepted
    ):
        return True
    for c in value.get("coding") or []:
        if isinstance(c, dict) and _matches_pair(c.get("system"), c.get("code"), accepted):
            return True
    return False


def _matches_pair(system: Any, code: Any, accepted: set[tuple[str | None, str]]) -> bool:
    if code is None:
        return False
    return (system, str(code)) in accepted or (None, str(code)) in accepted
