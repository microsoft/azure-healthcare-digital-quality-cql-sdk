"""Top-level ``cql-sdk`` Typer application."""

from __future__ import annotations

import typer

from cql_sdk.cli.commands import compile as compile_cmd
from cql_sdk.cli.commands import inspect as inspect_cmd
from cql_sdk.cli.commands import package as package_cmd
from cql_sdk.cli.commands import run as run_cmd
from cql_sdk.cli.commands import validate as validate_cmd
from cql_sdk.version import __version__

app = typer.Typer(
    name="cql-sdk",
    help="Command-line tools for the cql-sdk Python package.",
    no_args_is_help=True,
    add_completion=False,
)

app.command("compile", help="Compile a CQL source file to ELM JSON.")(compile_cmd.compile_)
app.command("inspect", help="Print a human-readable summary of an ELM file.")(inspect_cmd.inspect)
app.command("validate", help="Validate operator coverage for an ELM file.")(validate_cmd.validate)
app.command("run", help="Evaluate a named definition in an ELM file.")(run_cmd.run)
app.command("package", help="Package an input directory of ELM/resources.")(package_cmd.package)


@app.callback()
def _root(
    version: bool = typer.Option(
        False, "--version", help="Show the cql-sdk version and exit.", is_eager=True
    ),
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit()


if __name__ == "__main__":  # pragma: no cover
    app()
