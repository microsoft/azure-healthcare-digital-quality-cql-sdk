"""``cql-sdk validate`` command."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from cql_sdk.elm.serialization.loader import load_library_from_path
from cql_sdk.invocation.toolkit import InvocationToolkit


def validate(elm_file: Path = typer.Argument(..., exists=True, readable=True)) -> None:
    library = load_library_from_path(elm_file)
    toolkit = InvocationToolkit()
    toolkit.register(library)
    missing = toolkit.validate(library.identifier)

    console = Console()
    if not missing:
        console.print(f"[green]OK[/green] - all ELM nodes in {library.identifier} are executable.")
        raise typer.Exit(code=0)

    console.print(f"[yellow]Warning[/yellow] - {len(missing)} unsupported ELM node type(s):")
    for t in sorted(missing):
        console.print(f"  - {t}")
    raise typer.Exit(code=1)
