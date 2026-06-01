"""``cql-sdk inspect`` command."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from cql_sdk.elm.serialization.loader import load_library_from_path


def inspect(elm_file: Path = typer.Argument(..., exists=True, readable=True)) -> None:
    library = load_library_from_path(elm_file)
    console = Console()

    console.print(f"[bold]Library:[/bold] {library.identifier}")
    if library.includes:
        console.print(f"[bold]Includes:[/bold] {', '.join(str(i) for i in library.includes)}")

    table = Table(title="Definitions", show_lines=False)
    table.add_column("Name")
    table.add_column("Access")
    table.add_column("Context")
    table.add_column("Expression type")
    for name, d in library.definitions.items():
        table.add_row(name, d.access_level, d.context or "-", d.expression.type or "-")
    console.print(table)

    if library.parameters:
        console.print(f"[bold]Parameters:[/bold] {', '.join(library.parameters)}")
