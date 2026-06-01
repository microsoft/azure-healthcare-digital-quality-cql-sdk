"""FHIR-aware RuntimeContext factory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cql_sdk.fhir.retrieve import BundleDataSource
from cql_sdk.fhir.terminology import StaticTerminologyProvider
from cql_sdk.runtime.context import RuntimeContext


def context_from_bundle(
    bundle: dict[str, Any],
    *,
    value_sets_dir: str | Path | None = None,
    **overrides: Any,
) -> RuntimeContext:
    """Create a :class:`RuntimeContext` backed by an in-memory FHIR bundle.

    Optionally accepts a directory of FHIR ``ValueSet`` resources to wire up
    a :class:`StaticTerminologyProvider`.
    """
    ctx = RuntimeContext.default(**overrides)
    ds = BundleDataSource(bundle)
    ctx.data_source = ds
    if ctx.subject is None:
        ctx.subject = ds.subject
    if value_sets_dir is not None and ctx.terminology is None:
        ctx.terminology = StaticTerminologyProvider(value_sets_dir)
    return ctx

