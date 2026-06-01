"""FHIR <-> CQL type conversion helpers.

Adapter seam: third-party FHIR models (``fhir.resources``, ``fhirclient``)
can be plugged in later without the base SDK hard-wiring any specific
model library.
"""

from __future__ import annotations

from typing import Any


def resource_id(resource: dict[str, Any]) -> str | None:
    return resource.get("id") if isinstance(resource, dict) else None


def resource_type(resource: dict[str, Any]) -> str | None:
    return resource.get("resourceType") if isinstance(resource, dict) else None
