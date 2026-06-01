"""``cql-sdk package`` command."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from cql_sdk.packaging.library_package import LibraryPackage


def package(
    input_dir: Path = typer.Argument(..., exists=True, file_okay=False, readable=True),
    output: Path = typer.Option(..., "--output", "-o", help="Output directory for the package."),
    name: str | None = typer.Option(None, "--name", help="Override the package name."),
) -> None:
    pkg = LibraryPackage.discover(input_dir, name=name)
    target = pkg.write(output)
    Console().print(f"[green]Packaged[/green] {pkg.manifest.name} -> {target}")
