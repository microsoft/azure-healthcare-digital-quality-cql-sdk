"""``cql-sdk run`` command."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from cql_sdk.elm.serialization.loader import load_library_from_path
from cql_sdk.fhir.context import context_from_bundle
from cql_sdk.invocation.toolkit import InvocationToolkit


def run(
    elm_file: Path = typer.Argument(..., exists=True, readable=True),
    definition: str = typer.Option(..., "--definition", "-d", help="Definition name to evaluate."),
    bundle: Path | None = typer.Option(
        None, "--bundle", help="Optional FHIR Bundle JSON to bind as the data source."
    ),
) -> None:
    library = load_library_from_path(elm_file)
    toolkit = InvocationToolkit()
    toolkit.register(library)

    context = None
    if bundle is not None:
        bundle_obj = json.loads(bundle.read_text(encoding="utf-8"))
        context = context_from_bundle(bundle_obj)

    result = toolkit.invoke(
        library_identifier=library.identifier,
        definition=definition,
        context=context,
    )
    Console().print_json(data={"definition": definition, "result": _json_safe(result)})


def _json_safe(value: object) -> object:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    return repr(value)
