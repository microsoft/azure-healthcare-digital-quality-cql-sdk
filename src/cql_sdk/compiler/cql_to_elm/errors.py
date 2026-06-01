"""Exceptions raised by the CQL → ELM front-end."""

from __future__ import annotations


class CqlError(Exception):
    """Base class for all CQL front-end errors."""

    def __init__(self, message: str, *, line: int | None = None, column: int | None = None) -> None:
        location = ""
        if line is not None:
            location = f" at line {line}"
            if column is not None:
                location += f", column {column}"
        super().__init__(message + location)
        self.message = message
        self.line = line
        self.column = column


class CqlLexError(CqlError):
    """Raised when the lexer encounters an unrecognized character."""


class CqlParseError(CqlError):
    """Raised when the parser cannot match the input against the supported grammar."""


class CqlTranslationError(CqlError):
    """Raised when the AST cannot be translated to ELM JSON."""
