"""Synthetic FHIRHelpers library + auto-registration helper.

The real FHIRHelpers.cql contains a large block of ToXxx adapter functions
and a few named codes that referencing measures expect to resolve. Bundling
the full source would require compiling it on package import, which slows
startup and pulls in the CQL parser eagerly. Instead, this module exposes a
small synthetic library with just the codes/expression refs we have seen in
the field. Measures that need more can register a fuller library themselves.
"""

from __future__ import annotations

from typing import Any

from cql_sdk.elm.models.library import Library, LibraryIdentifier

_FHIR_CONDITION_CLINICAL_STATUS = "http://terminology.hl7.org/CodeSystem/condition-clinical"


def synthetic_fhir_helpers() -> Library:
    """Build a synthetic FHIRHelpers library exposing common named codes."""
    code_systems: dict[str, dict[str, Any]] = {
        "ConditionClinicalStatusCodes": {
            "name": "ConditionClinicalStatusCodes",
            "id": _FHIR_CONDITION_CLINICAL_STATUS,
        },
        "ConditionVerificationStatusCodes": {
            "name": "ConditionVerificationStatusCodes",
            "id": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
        },
    }

    codes: dict[str, dict[str, Any]] = {
        # The named codes most commonly referenced by measures via
        # `Global."active"` or `FHIRHelpers."active"` are the
        # ConditionClinicalStatus values.
        "active": {
            "name": "active",
            "id": "active",
            "display": "Active",
            "codeSystem": {"name": "ConditionClinicalStatusCodes"},
        },
        "recurrence": {
            "name": "recurrence",
            "id": "recurrence",
            "display": "Recurrence",
            "codeSystem": {"name": "ConditionClinicalStatusCodes"},
        },
        "relapse": {
            "name": "relapse",
            "id": "relapse",
            "display": "Relapse",
            "codeSystem": {"name": "ConditionClinicalStatusCodes"},
        },
        "confirmed": {
            "name": "confirmed",
            "id": "confirmed",
            "display": "Confirmed",
            "codeSystem": {"name": "ConditionVerificationStatusCodes"},
        },
    }

    return Library(
        identifier=LibraryIdentifier(id="FHIRHelpers", version="4.0.1"),
        code_systems=code_systems,
        codes=codes,
        raw={
            "library": {
                "identifier": {"id": "FHIRHelpers", "version": "4.0.1"},
                "codeSystems": {
                    "def": list(code_systems.values()),
                },
                "codes": {
                    "def": list(codes.values()),
                },
            }
        },
    )
