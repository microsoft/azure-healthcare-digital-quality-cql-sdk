"""Adapters wiring FHIR-specific providers into a :class:`RuntimeContext`."""

from __future__ import annotations

from typing import Any

from cql_sdk.abstractions.terminology import TerminologyProvider
from cql_sdk.fhir.context import context_from_bundle


def build_context(
    *,
    bundle: dict[str, Any] | None = None,
    terminology: TerminologyProvider | None = None,
) -> Any:
    ctx = context_from_bundle(bundle or {"resourceType": "Bundle", "entry": []})
    ctx.terminology = terminology
    return ctx
