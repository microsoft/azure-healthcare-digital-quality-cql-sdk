"""CQL lexer.

Produces a flat token stream from CQL source text. Whitespace and comments
are skipped. Multi-word CQL operators (``starts during``, ``is not null``,
``date from``, ``start of``, ``end of``, ``singleton from``) remain as
adjacent single-word tokens; the parser fuses them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto

from cql_sdk.compiler.cql_to_elm.errors import CqlLexError


class TokenKind(Enum):
    KEYWORD = auto()
    IDENT = auto()             # unquoted identifier
    QUOTED_IDENT = auto()      # "..." -> identifier (define name, code/valueset name, etc.)
    STRING = auto()            # '...' -> string literal
    INTEGER = auto()
    DECIMAL = auto()
    DATETIME = auto()           # @YYYY-MM-DD[Thh:mm:ss[.f]]
    OP = auto()                 # = != < <= > >= ~ + - * /
    PUNCT = auto()              # . , : ; ( ) [ ] { }
    EOF = auto()


@dataclass(slots=True)
class Token:
    kind: TokenKind
    value: str
    line: int
    column: int

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"Token({self.kind.name}, {self.value!r}, line={self.line})"


# CQL 1.5 keywords (lowercase, case-sensitive per spec).
KEYWORDS: frozenset[str] = frozenset({
    "after",
    "and",
    "as",
    "before",
    "by",
    "called",
    "case",
    "code",
    "codesystem",
    "concept",
    "context",
    "date",
    "default",
    "define",
    "desc",
    "asc",
    "display",
    "during",
    "else",
    "end",
    "ends",
    "exists",
    "false",
    "flatten",
    "from",
    "function",
    "if",
    "in",
    "include",
    "is",
    "Interval",
    "List",
    "let",
    "library",
    "not",
    "null",
    "of",
    "or",
    "overlaps",
    "parameter",
    "return",
    "singleton",
    "sort",
    "start",
    "starts",
    "such",
    "that",
    "then",
    "true",
    "using",
    "valueset",
    "version",
    "when",
    "where",
    "with",
})


# Punctuation single-chars
_PUNCT_CHARS = set(".,:;()[]{}")

# Multi-char operators tried first (longer match wins).
_OPERATORS = ("!=", "<=", ">=", "=", "<", ">", "~", "+", "-", "*", "/")

# DateTime literal pattern, anchored at @.
_DATETIME_RE = re.compile(
    r"@(\d{4}(?:-\d{2}(?:-\d{2}(?:T\d{2}(?::\d{2}(?::\d{2}(?:\.\d+)?)?)?)?)?)?)"
)

# Integer / decimal numbers.
_NUMBER_RE = re.compile(r"\d+(\.\d+)?")

# Unquoted identifier.
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def tokenize(text: str) -> list[Token]:
    """Tokenize ``text`` and return a flat token list ending with EOF."""
    tokens: list[Token] = []
    i = 0
    line = 1
    line_start = 0

    def col_at(pos: int) -> int:
        return pos - line_start + 1

    n = len(text)
    while i < n:
        ch = text[i]

        # Whitespace
        if ch == "\n":
            line += 1
            line_start = i + 1
            i += 1
            continue
        if ch in " \t\r":
            i += 1
            continue

        # Line comment
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i + 2)
            i = n if j == -1 else j
            continue

        # Block comment
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            if j == -1:
                raise CqlLexError("Unterminated block comment", line=line, column=col_at(i))
            # Advance line counter through the block.
            for k in range(i, j + 2):
                if text[k] == "\n":
                    line += 1
                    line_start = k + 1
            i = j + 2
            continue

        # DateTime literal
        if ch == "@":
            m = _DATETIME_RE.match(text, i)
            if not m:
                raise CqlLexError("Invalid @ datetime literal", line=line, column=col_at(i))
            tokens.append(Token(TokenKind.DATETIME, m.group(0), line, col_at(i)))
            i = m.end()
            continue

        # Single-quoted string literal
        if ch == "'":
            j = i + 1
            chars: list[str] = []
            while j < n and text[j] != "'":
                if text[j] == "\\" and j + 1 < n:
                    chars.append(text[j + 1])
                    j += 2
                    continue
                if text[j] == "\n":
                    raise CqlLexError("Unterminated string literal", line=line, column=col_at(i))
                chars.append(text[j])
                j += 1
            if j >= n:
                raise CqlLexError("Unterminated string literal", line=line, column=col_at(i))
            tokens.append(Token(TokenKind.STRING, "".join(chars), line, col_at(i)))
            i = j + 1
            continue

        # Double-quoted identifier
        if ch == '"':
            j = i + 1
            while j < n and text[j] != '"':
                if text[j] == "\n":
                    raise CqlLexError("Unterminated quoted identifier", line=line, column=col_at(i))
                j += 1
            if j >= n:
                raise CqlLexError("Unterminated quoted identifier", line=line, column=col_at(i))
            tokens.append(Token(TokenKind.QUOTED_IDENT, text[i + 1 : j], line, col_at(i)))
            i = j + 1
            continue

        # Number (integer or decimal)
        if ch.isdigit():
            m = _NUMBER_RE.match(text, i)
            assert m is not None
            literal = m.group(0)
            kind = TokenKind.DECIMAL if "." in literal else TokenKind.INTEGER
            tokens.append(Token(kind, literal, line, col_at(i)))
            i = m.end()
            continue

        # Identifier / keyword
        if ch == "_" or ch.isalpha():
            m = _IDENT_RE.match(text, i)
            assert m is not None
            literal = m.group(0)
            kind = TokenKind.KEYWORD if literal in KEYWORDS else TokenKind.IDENT
            tokens.append(Token(kind, literal, line, col_at(i)))
            i = m.end()
            continue

        # Punctuation
        if ch in _PUNCT_CHARS:
            tokens.append(Token(TokenKind.PUNCT, ch, line, col_at(i)))
            i += 1
            continue

        # Operators (longest match first)
        matched = False
        for op in _OPERATORS:
            if text.startswith(op, i):
                tokens.append(Token(TokenKind.OP, op, line, col_at(i)))
                i += len(op)
                matched = True
                break
        if matched:
            continue

        raise CqlLexError(f"Unexpected character {ch!r}", line=line, column=col_at(i))

    tokens.append(Token(TokenKind.EOF, "", line, col_at(i)))
    return tokens
