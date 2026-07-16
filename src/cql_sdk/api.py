"""High-level convenience facade for the cql-sdk package.

This module is the preferred public entry point for most users. It delegates
to :mod:`cql_sdk.invocation.toolkit` but offers a minimal, explicit surface
so consumers never have to touch lower-level modules such as
:mod:`cql_sdk.compiler` or :mod:`cql_sdk.runtime`.

Typical workflow::

    from cql_sdk.api import load_library, invoke

    lib = load_library("HelloWorld.elm.json")
    result = invoke(lib, definition="Greeting")

To start from CQL source instead of pre-translated ELM, use
:func:`load_library_from_cql` or :func:`load_library_from_cql_text`.

For repeated invocations or more advanced wiring (custom terminology, FHIR
retrieval, caching), use :class:`cql_sdk.invocation.toolkit.InvocationToolkit`
directly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cql_sdk.compiler.cql_to_elm import compile_file, translate
from cql_sdk.dqm.package import MeasurePackage
from cql_sdk.dqm.results import MeasureResult
from cql_sdk.elm.models.library import Library
from cql_sdk.elm.serialization.loader import load_library_from_path, load_library_from_string
from cql_sdk.invocation.toolkit import InvocationToolkit
from cql_sdk.runtime.context import RuntimeContext

__all__ = [
    "create_context",
    "evaluate_measure_package",
    "invoke",
    "load_library",
    "load_library_from_cql",
    "load_library_from_cql_text",
    "load_library_from_text",
    "load_measure_package",
]


def load_library(path: str | Path) -> Library:
    """Load an ELM library from a JSON file on disk."""
    return load_library_from_path(Path(path))


def load_library_from_text(text: str) -> Library:
    """Load an ELM library from a JSON string."""
    return load_library_from_string(text)


def load_library_from_cql(path: str | Path) -> Library:
    """Compile a ``.cql`` source file and return the resulting Library."""
    elm = compile_file(path)
    return load_library_from_string(json.dumps(elm))


def load_library_from_cql_text(text: str) -> Library:
    """Compile a CQL source string and return the resulting Library."""
    elm = translate(text)
    return load_library_from_string(json.dumps(elm))


def create_context(**overrides: Any) -> RuntimeContext:
    """Build a default :class:`RuntimeContext` with optional overrides."""
    return RuntimeContext.default(**overrides)


def load_measure_package(directory: str | Path) -> MeasurePackage:
    """Load a DQM (FHIR/QI-Core) measure package from a directory.

    The directory holds the FHIR ``Measure`` resource, its ELM libraries, and
    the expanded value sets. See :class:`cql_sdk.dqm.MeasurePackage`.
    """
    return MeasurePackage.load(directory)


def evaluate_measure_package(
    directory: str | Path,
    bundle: dict[str, Any],
    *,
    period: Any | None = None,
) -> MeasureResult:
    """Load a measure package and evaluate it against a single FHIR ``bundle``."""
    return MeasurePackage.load(directory).evaluate(bundle, period=period)


def invoke(
    library: Library,
    *,
    definition: str,
    parameters: dict[str, Any] | None = None,
    context: RuntimeContext | None = None,
) -> Any:
    """Invoke a named definition on a loaded library.

    Args:
        library: A previously loaded ELM library.
        definition: Name of the ``def`` (or function) to evaluate.
        parameters: Optional parameter bindings.
        context: Optional pre-built runtime context; a default one is
            created if omitted.

    Returns:
        The evaluated result. For scalar definitions this is typically a
        Python primitive; for list-valued definitions a list is returned.
    """
    toolkit = InvocationToolkit()
    toolkit.register(library)
    return toolkit.invoke(
        library_identifier=library.identifier,
        definition=definition,
        parameters=parameters,
        context=context,
    )
