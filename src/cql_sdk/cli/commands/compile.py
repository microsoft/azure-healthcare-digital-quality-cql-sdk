"""``cql-sdk compile`` command — turn a ``.cql`` file into ELM JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from rich.console import Console

from cql_sdk.compiler.cql_to_elm import compile_file


def compile_(
    cql_file: Path = typer.Argument(..., exists=True, readable=True, help="Path to a .cql file."),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write ELM JSON to this path. Defaults to stdout.",
    ),
    indent: int = typer.Option(
        2,
        "--indent",
        min=0,
        help="JSON indentation level (0 = single line).",
    ),
) -> None:
    elm = compile_file(cql_file)
    payload = json.dumps(elm, indent=indent if indent > 0 else None, sort_keys=False)
    if output is None:
        sys.stdout.write(payload)
        sys.stdout.write("\n")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload, encoding="utf-8")
    Console(stderr=True).print(f"[green]Wrote ELM JSON to[/green] {output}")
