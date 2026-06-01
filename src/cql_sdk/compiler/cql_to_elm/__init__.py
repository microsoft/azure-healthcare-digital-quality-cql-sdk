"""Pure-Python CQL → ELM JSON front-end.

Supports a deliberately small but practically useful subset of CQL 1.5 — see
:mod:`cql_sdk.compiler.cql_to_elm.parser` for the grammar that is actually
accepted. The output is an ELM JSON document directly consumable by
:func:`cql_sdk.elm.serialization.loader.load_library_from_string`.

Public entry points are :func:`translate` and :func:`compile_file`. Everything
else in this sub-package is considered internal.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cql_sdk.compiler.cql_to_elm import errors
from cql_sdk.compiler.cql_to_elm.lexer import tokenize
from cql_sdk.compiler.cql_to_elm.parser import parse
from cql_sdk.compiler.cql_to_elm.translator import translate_library

__all__ = [
    "CqlError",
    "CqlLexError",
    "CqlParseError",
    "CqlTranslationError",
    "compile_file",
    "compile_text",
    "translate",
]

CqlError = errors.CqlError
CqlLexError = errors.CqlLexError
CqlParseError = errors.CqlParseError
CqlTranslationError = errors.CqlTranslationError


def translate(text: str) -> dict[str, Any]:
    """Translate a CQL source string to an ELM JSON document (Python dict).

    The returned dict is wrapped in a top-level ``{"library": {...}}`` envelope,
    matching what :func:`cql_sdk.elm.serialization.loader.load_library_from_string`
    expects.

    Raises:
        CqlLexError: tokenization failed.
        CqlParseError: parsing failed.
        CqlTranslationError: AST to ELM translation failed.
    """
    tokens = tokenize(text)
    ast = parse(tokens)
    return translate_library(ast)


def compile_text(text: str) -> dict[str, Any]:
    """Alias for :func:`translate`. Mirrors the C# Firely SDK naming."""
    return translate(text)


def compile_file(path: str | Path) -> dict[str, Any]:
    """Read a ``.cql`` file from disk and return its ELM JSON document."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"CQL file not found: {p}")
    return translate(p.read_text(encoding="utf-8"))
