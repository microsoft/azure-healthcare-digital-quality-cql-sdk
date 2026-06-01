import pytest

from cql_sdk.compiler.cql_to_elm.lexer import TokenKind, tokenize


@pytest.mark.unit
def test_tokenize_keywords_and_idents():
    tokens = tokenize("library Foo version '1.0'")
    kinds = [t.kind for t in tokens[:-1]]
    values = [t.value for t in tokens[:-1]]
    assert kinds == [
        TokenKind.KEYWORD,  # library
        TokenKind.IDENT,    # Foo
        TokenKind.KEYWORD,  # version
        TokenKind.STRING,   # '1.0'
    ]
    assert values == ["library", "Foo", "version", "1.0"]


@pytest.mark.unit
def test_tokenize_quoted_identifier_vs_string():
    tokens = tokenize('"Initial Population" \'final\'')
    kinds = [t.kind for t in tokens[:-1]]
    values = [t.value for t in tokens[:-1]]
    assert kinds == [TokenKind.QUOTED_IDENT, TokenKind.STRING]
    assert values == ["Initial Population", "final"]


@pytest.mark.unit
def test_tokenize_skips_comments():
    src = """\
// leading comment
library Foo // trailing
/* block
   comment */
version '1'
"""
    tokens = [t for t in tokenize(src) if t.kind is not TokenKind.EOF]
    assert [t.value for t in tokens] == ["library", "Foo", "version", "1"]


@pytest.mark.unit
def test_tokenize_datetime_and_numbers():
    tokens = tokenize("@2025-01-01T00:00:00.0 42 3.14")
    kinds = [t.kind for t in tokens[:-1]]
    assert kinds == [TokenKind.DATETIME, TokenKind.INTEGER, TokenKind.DECIMAL]


@pytest.mark.unit
def test_tokenize_multi_char_operators():
    tokens = tokenize("a <= b != c >= d")
    op_values = [t.value for t in tokens if t.kind is TokenKind.OP]
    assert op_values == ["<=", "!=", ">="]
