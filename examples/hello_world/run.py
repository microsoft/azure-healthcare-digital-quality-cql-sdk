"""Minimal end-to-end hello-world example.

Run from the repository root::

    uv run python examples/hello_world/run.py
"""

from __future__ import annotations

from pathlib import Path

from cql_sdk.api import invoke, load_library

ELM = Path(__file__).with_name("HelloWorld.elm.json")


def main() -> None:
    library = load_library(ELM)
    print(f"Library: {library.identifier}")
    print(f"Greeting = {invoke(library, definition='Greeting')!r}")
    print(f"Sum      = {invoke(library, definition='Sum')!r}")


if __name__ == "__main__":
    main()
