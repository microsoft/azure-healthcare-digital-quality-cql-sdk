"""Recursive-descent parser for a CQL 1.5 subset.

The accepted grammar covers the surface used by the project's three measure
files plus a handful of generally useful constructs:

* Header: ``library``, ``using``, ``include``, ``codesystem``, ``valueset``,
  ``code``, ``parameter``, ``context``, ``define``.
* Expressions: literals (boolean / integer / decimal / string / null /
  datetime / quantity), references (quoted + unquoted), property access,
  function calls, unary operators (``not``, ``exists``, ``-``, ``is null``,
  ``is not null``, ``start of``, ``end of``, ``date from``, ``singleton from``,
  ``flatten``), binary operators (``and``, ``or``, ``=``, ``!=``, ``~``,
  ``<``, ``<=``, ``>``, ``>=``, ``+``, ``-``, ``*``, ``/``,
  ``in``, ``during``, ``overlaps``, ``before``, ``after``, ``ends during``,
  ``starts during``), casts (``X as T``), interval constructors
  (``Interval[a, b]``), list literals (``{...}``), retrieves
  (``[Encounter: "VS"]``), and query expressions (``alias where … sort …
  return …``).

Anything outside that subset raises :class:`CqlParseError`.
"""

from __future__ import annotations

from cql_sdk.compiler.cql_to_elm import ast as A
from cql_sdk.compiler.cql_to_elm.errors import CqlParseError
from cql_sdk.compiler.cql_to_elm.lexer import Token, TokenKind

_TYPE_KEYWORDS = {"Interval", "List", "date", "code", "concept"}

_COMPARE_OPS = {"=", "!=", "<", "<=", ">", ">=", "~"}
_ADDITIVE_OPS = {"+", "-"}
_MULT_OPS = {"*", "/"}

# CQL allows alias identifiers to be unquoted single-token names. We use a
# small heuristic in the postfix path to distinguish "expression followed by
# alias" from "expression standing alone". Aliases must be unquoted IDENT
# tokens that are not CQL keywords.


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    # --- token helpers ------------------------------------------------------

    def _peek(self, offset: int = 0) -> Token:
        return self.tokens[min(self.pos + offset, len(self.tokens) - 1)]

    def _advance(self) -> Token:
        tok = self.tokens[self.pos]
        if tok.kind is not TokenKind.EOF:
            self.pos += 1
        return tok

    def _match(self, kind: TokenKind, value: str | None = None) -> bool:
        tok = self._peek()
        if tok.kind is not kind:
            return False
        if value is not None and tok.value != value:
            return False
        self._advance()
        return True

    def _check(self, kind: TokenKind, value: str | None = None) -> bool:
        tok = self._peek()
        if tok.kind is not kind:
            return False
        return value is None or tok.value == value

    def _check_keyword_pair(self, first: str, second: str) -> bool:
        """Return True iff the next two tokens are KEYWORD ``first`` then KEYWORD ``second``."""
        if not self._check(TokenKind.KEYWORD, first):
            return False
        nxt = self._peek(1)
        return nxt.kind is TokenKind.KEYWORD and nxt.value == second

    def _expect(self, kind: TokenKind, value: str | None = None) -> Token:
        tok = self._peek()
        if tok.kind is not kind or (value is not None and tok.value != value):
            expected = value if value is not None else kind.name
            raise CqlParseError(
                f"Expected {expected!r}, got {tok.value!r} ({tok.kind.name})",
                line=tok.line,
                column=tok.column,
            )
        return self._advance()

    def _expect_keyword(self, value: str) -> Token:
        return self._expect(TokenKind.KEYWORD, value)

    def _expect_punct(self, value: str) -> Token:
        return self._expect(TokenKind.PUNCT, value)

    def _expect_op(self, value: str) -> Token:
        return self._expect(TokenKind.OP, value)

    def _is_ident_like(self, tok: Token) -> bool:
        return tok.kind in (TokenKind.IDENT, TokenKind.QUOTED_IDENT)

    # --- top-level ----------------------------------------------------------

    def parse_library(self) -> A.Library:
        ident = self._parse_library_header()
        usings: list[A.Using] = []
        includes: list[A.Include] = []
        code_systems: list[A.CodeSystemDef] = []
        value_sets: list[A.ValueSetDef] = []
        codes: list[A.CodeDef] = []
        parameters: list[A.ParameterDef] = []
        statements: list[A.StatementDef] = []
        context: str | None = None

        while self._peek().kind is not TokenKind.EOF:
            tok = self._peek()
            if tok.kind is TokenKind.KEYWORD:
                kw = tok.value
                if kw == "using":
                    usings.append(self._parse_using())
                    continue
                if kw == "include":
                    includes.append(self._parse_include())
                    continue
                if kw == "codesystem":
                    code_systems.append(self._parse_codesystem())
                    continue
                if kw == "valueset":
                    value_sets.append(self._parse_valueset())
                    continue
                if kw == "code":
                    codes.append(self._parse_code())
                    continue
                if kw == "parameter":
                    parameters.append(self._parse_parameter())
                    continue
                if kw == "context":
                    self._advance()
                    ctx_tok = self._advance()
                    if ctx_tok.kind not in (TokenKind.IDENT, TokenKind.KEYWORD):
                        raise CqlParseError(
                            f"Expected context name, got {ctx_tok.value!r}",
                            line=ctx_tok.line,
                            column=ctx_tok.column,
                        )
                    context = ctx_tok.value
                    continue
                if kw == "define":
                    statements.append(self._parse_define())
                    continue
            raise CqlParseError(
                f"Unexpected token {tok.value!r} at top level",
                line=tok.line,
                column=tok.column,
            )

        return A.Library(
            identifier=ident,
            usings=usings,
            includes=includes,
            code_systems=code_systems,
            value_sets=value_sets,
            codes=codes,
            parameters=parameters,
            context=context,
            statements=statements,
        )

    # --- header productions -------------------------------------------------

    def _parse_library_header(self) -> A.LibraryIdent:
        self._expect_keyword("library")
        name_tok = self._advance()
        if not self._is_ident_like(name_tok):
            raise CqlParseError(
                f"Expected library name, got {name_tok.value!r}",
                line=name_tok.line,
                column=name_tok.column,
            )
        version: str | None = None
        if self._match(TokenKind.KEYWORD, "version"):
            version = self._expect(TokenKind.STRING).value
        return A.LibraryIdent(id=name_tok.value, version=version)

    def _parse_using(self) -> A.Using:
        self._expect_keyword("using")
        name_tok = self._advance()
        if not self._is_ident_like(name_tok):
            raise CqlParseError("Expected model name after 'using'", line=name_tok.line)
        version: str | None = None
        if self._match(TokenKind.KEYWORD, "version"):
            version = self._expect(TokenKind.STRING).value
        return A.Using(name=name_tok.value, version=version)

    def _parse_include(self) -> A.Include:
        self._expect_keyword("include")
        name_tok = self._advance()
        if not self._is_ident_like(name_tok):
            raise CqlParseError("Expected library name after 'include'", line=name_tok.line)
        version: str | None = None
        if self._match(TokenKind.KEYWORD, "version"):
            version = self._expect(TokenKind.STRING).value
        alias: str | None = None
        if self._match(TokenKind.KEYWORD, "called"):
            alias_tok = self._advance()
            if not self._is_ident_like(alias_tok):
                raise CqlParseError("Expected alias after 'called'", line=alias_tok.line)
            alias = alias_tok.value
        return A.Include(name=name_tok.value, version=version, alias=alias)

    def _parse_codesystem(self) -> A.CodeSystemDef:
        self._expect_keyword("codesystem")
        name = self._expect(TokenKind.QUOTED_IDENT).value
        self._expect_punct(":")
        uri = self._expect(TokenKind.STRING).value
        return A.CodeSystemDef(name=name, uri=uri)

    def _parse_valueset(self) -> A.ValueSetDef:
        self._expect_keyword("valueset")
        name = self._expect(TokenKind.QUOTED_IDENT).value
        self._expect_punct(":")
        uri = self._expect(TokenKind.STRING).value
        return A.ValueSetDef(name=name, uri=uri)

    def _parse_code(self) -> A.CodeDef:
        self._expect_keyword("code")
        name = self._expect(TokenKind.QUOTED_IDENT).value
        self._expect_punct(":")
        code_value = self._expect(TokenKind.STRING).value
        self._expect_keyword("from")
        code_system = self._expect(TokenKind.QUOTED_IDENT).value
        display: str | None = None
        if self._match(TokenKind.KEYWORD, "display"):
            display = self._expect(TokenKind.STRING).value
        return A.CodeDef(name=name, code=code_value, code_system=code_system, display=display)

    def _parse_parameter(self) -> A.ParameterDef:
        self._expect_keyword("parameter")
        name_tok = self._advance()
        if name_tok.kind not in (TokenKind.QUOTED_IDENT, TokenKind.IDENT):
            raise CqlParseError("Expected parameter name", line=name_tok.line)
        type_spec: A.TypeSpec | None = None
        default: A.Expr | None = None
        if not self._check(TokenKind.KEYWORD, "default") and not self._check_define_start_or_top():
            type_spec = self._parse_type_specifier_if_present()
        if self._match(TokenKind.KEYWORD, "default"):
            default = self._parse_expression()
        return A.ParameterDef(name=name_tok.value, type_specifier=type_spec, default=default)

    def _check_define_start_or_top(self) -> bool:
        tok = self._peek()
        return tok.kind is TokenKind.KEYWORD and tok.value in {
            "define",
            "parameter",
            "valueset",
            "codesystem",
            "code",
            "context",
            "include",
            "using",
        }

    def _parse_define(self) -> A.StatementDef:
        self._expect_keyword("define")
        name_tok = self._advance()
        if name_tok.kind not in (TokenKind.QUOTED_IDENT, TokenKind.IDENT):
            raise CqlParseError("Expected define name", line=name_tok.line)
        self._expect_punct(":")
        expr = self._parse_expression()
        return A.StatementDef(name=name_tok.value, expression=expr)

    # --- type specifiers ----------------------------------------------------

    def _parse_type_specifier_if_present(self) -> A.TypeSpec | None:
        tok = self._peek()
        if tok.kind is TokenKind.KEYWORD and tok.value in _TYPE_KEYWORDS:
            return self._parse_type_specifier()
        if tok.kind is TokenKind.IDENT and tok.value[:1].isupper():
            return self._parse_type_specifier()
        return None

    def _parse_type_specifier(self) -> A.TypeSpec:
        tok = self._advance()
        name = tok.value
        argument: A.TypeSpec | None = None
        # Generic argument: Interval<DateTime>, List<Encounter>
        if self._check(TokenKind.OP, "<"):
            self._advance()
            argument = self._parse_type_specifier()
            self._expect_op(">")
        return A.TypeSpec(name=name, argument=argument)

    # --- expression precedence ladder --------------------------------------

    def _parse_expression(self) -> A.Expr:
        return self._parse_or()

    def _parse_or(self) -> A.Expr:
        left = self._parse_and()
        while self._match(TokenKind.KEYWORD, "or"):
            right = self._parse_and()
            left = A.BinaryOp(op="or", left=left, right=right)
        return left

    def _parse_and(self) -> A.Expr:
        left = self._parse_not()
        while self._match(TokenKind.KEYWORD, "and"):
            right = self._parse_not()
            left = A.BinaryOp(op="and", left=left, right=right)
        return left

    def _parse_not(self) -> A.Expr:
        if self._match(TokenKind.KEYWORD, "not"):
            return A.UnaryOp(op="not", operand=self._parse_not())
        return self._parse_compare()

    def _parse_compare(self) -> A.Expr:
        left = self._parse_interval_relation()
        # Equality / equivalence / ordering — left-associative single chain.
        if self._peek().kind is TokenKind.OP and self._peek().value in _COMPARE_OPS:
            op = self._advance().value
            right = self._parse_interval_relation()
            return A.BinaryOp(op=op, left=left, right=right)
        return left

    def _parse_interval_relation(self) -> A.Expr:
        left = self._parse_additive()
        while True:
            # "X is null" / "X is not null"
            if self._match(TokenKind.KEYWORD, "is"):
                negated = self._match(TokenKind.KEYWORD, "not")
                self._expect_keyword("null")
                left = A.UnaryOp(
                    op="is not null" if negated else "is null",
                    operand=left,
                )
                continue
            # "X in <expr>"
            if self._match(TokenKind.KEYWORD, "in"):
                right = self._parse_additive()
                left = A.BinaryOp(op="in", left=left, right=right)
                continue
            # "X during <interval>"
            if self._match(TokenKind.KEYWORD, "during"):
                right = self._parse_additive()
                left = A.BinaryOp(op="during", left=left, right=right)
                continue
            # "X overlaps <interval>"
            if self._match(TokenKind.KEYWORD, "overlaps"):
                right = self._parse_additive()
                left = A.BinaryOp(op="overlaps", left=left, right=right)
                continue
            # "X before <expr>" / "X before end of <expr>"
            if self._match(TokenKind.KEYWORD, "before"):
                right = self._parse_additive()
                left = A.BinaryOp(op="before", left=left, right=right)
                continue
            if self._match(TokenKind.KEYWORD, "after"):
                right = self._parse_additive()
                left = A.BinaryOp(op="after", left=left, right=right)
                continue
            # "X ends during <interval>" / "X starts during <interval>"
            if self._check_keyword_pair("ends", "during"):
                self._advance()
                self._advance()
                right = self._parse_additive()
                left = A.BinaryOp(op="ends during", left=left, right=right)
                continue
            if self._check_keyword_pair("starts", "during"):
                self._advance()
                self._advance()
                right = self._parse_additive()
                left = A.BinaryOp(op="starts during", left=left, right=right)
                continue
            break
        return left

    def _parse_additive(self) -> A.Expr:
        left = self._parse_multiplicative()
        while self._peek().kind is TokenKind.OP and self._peek().value in _ADDITIVE_OPS:
            op = self._advance().value
            right = self._parse_multiplicative()
            # If the right-hand side is a bare numeric literal directly
            # followed by a duration-unit identifier (e.g. ``+ 6 months``),
            # the literal is actually a Quantity. Promote it so the runtime
            # can apply calendar arithmetic.
            unit = self._consume_duration_unit_suffix()
            if unit is not None and isinstance(right, A.IntLit | A.DecimalLit):
                lit_value = str(right.value) if isinstance(right, A.IntLit) else right.text
                right = A.QuantityLit(value=lit_value, unit=unit)
            left = A.BinaryOp(op=op, left=left, right=right)
        # Drop any trailing duration unit that wasn't already consumed.
        self._consume_duration_unit_suffix()
        return left

    def _consume_duration_unit_suffix(self) -> str | None:
        tok = self._peek()
        if tok.kind is TokenKind.IDENT and tok.value in {
            "year", "years", "month", "months", "week", "weeks",
            "day", "days", "hour", "hours", "minute", "minutes",
            "second", "seconds", "millisecond", "milliseconds",
        }:
            self._advance()
            return tok.value
        return None

    def _parse_multiplicative(self) -> A.Expr:
        left = self._parse_cast()
        while self._peek().kind is TokenKind.OP and self._peek().value in _MULT_OPS:
            op = self._advance().value
            right = self._parse_cast()
            left = A.BinaryOp(op=op, left=left, right=right)
        return left

    def _parse_cast(self) -> A.Expr:
        operand = self._parse_unary()
        while self._match(TokenKind.KEYWORD, "as"):
            target = self._parse_type_specifier()
            operand = A.Cast(operand=operand, target=target)
        return operand

    def _parse_unary(self) -> A.Expr:
        # ``duration in <precision> of <expr>`` is a single CQL operator with a
        # precision argument; emit a dedicated AST node so the translator can
        # produce a ``DurationBetween``-shaped ELM node.
        if (
            self._check(TokenKind.IDENT, "duration")
            and self._peek(1).kind is TokenKind.KEYWORD
            and self._peek(1).value == "in"
        ):
            self._advance()  # duration
            self._advance()  # in
            precision_tok = self._advance()
            if precision_tok.kind not in (TokenKind.IDENT, TokenKind.KEYWORD):
                raise CqlParseError(
                    "Expected precision identifier after 'duration in'",
                    line=precision_tok.line,
                    column=precision_tok.column,
                )
            self._expect_keyword("of")
            operand = self._parse_unary()
            return A.DurationOf(precision=precision_tok.value, operand=operand)

        # Multi-word unaries.
        if self._check_keyword_pair("start", "of"):
            self._advance()
            self._advance()
            return A.UnaryOp(op="start of", operand=self._parse_unary())
        if self._check_keyword_pair("end", "of"):
            self._advance()
            self._advance()
            return A.UnaryOp(op="end of", operand=self._parse_unary())
        if self._check_keyword_pair("date", "from"):
            self._advance()
            self._advance()
            return A.UnaryOp(op="date from", operand=self._parse_unary())
        if self._check_keyword_pair("singleton", "from"):
            self._advance()
            self._advance()
            return A.UnaryOp(op="singleton from", operand=self._parse_unary())
        if self._match(TokenKind.KEYWORD, "exists"):
            return A.UnaryOp(op="exists", operand=self._parse_unary())
        if self._match(TokenKind.KEYWORD, "flatten"):
            return A.UnaryOp(op="flatten", operand=self._parse_unary())
        if self._peek().kind is TokenKind.OP and self._peek().value == "-":
            # Unary minus: only treat as such if the next token wouldn't make sense binary.
            # In practice we only need this in front of literals; binary minus is handled
            # at the additive level.
            self._advance()
            return A.UnaryOp(op="-", operand=self._parse_unary())
        return self._parse_postfix(self._parse_primary())

    def _parse_postfix(self, expr: A.Expr) -> A.Expr:
        while True:
            # Property access: x.field, optionally followed by a paren'd argument
            # list ``x.method(arg, ...)`` — modelled as a fluent function call
            # (FunctionRef whose first operand is the receiver).
            if self._check(TokenKind.PUNCT, "."):
                self._advance()
                path_tok = self._advance()
                _IDENT_LIKE = (
                    TokenKind.IDENT,
                    TokenKind.QUOTED_IDENT,
                    TokenKind.KEYWORD,
                )
                if path_tok.kind not in _IDENT_LIKE:
                    raise CqlParseError(
                        f"Expected property name after '.', got {path_tok.value!r}",
                        line=path_tok.line,
                        column=path_tok.column,
                    )
                if self._check(TokenKind.PUNCT, "("):
                    self._advance()
                    args: list[A.Expr] = []
                    if not self._check(TokenKind.PUNCT, ")"):
                        args.append(self._parse_expression())
                        while self._match(TokenKind.PUNCT, ","):
                            args.append(self._parse_expression())
                    self._expect_punct(")")
                    expr = A.FunctionCall(
                        name=path_tok.value, args=[expr, *args], library=None
                    )
                else:
                    expr = A.PropertyAccess(source=expr, path=path_tok.value)
                continue

            # Query continuation: "<expr> <alias> [where|sort|return]"
            if self._is_alias_continuation(expr):
                expr = self._parse_query_from(expr)
                continue
            break
        return expr

    _ALIAS_CONTINUATION_TYPES = (
        A.Retrieve,
        A.Ref,
        A.Query,
        A.UnaryOp,
        A.FunctionCall,
        A.PropertyAccess,
    )
    _QUERY_CLAUSE_KEYWORDS = frozenset({"where", "sort", "return"})

    def _is_alias_continuation(self, expr: A.Expr) -> bool:
        # Only retrieves, Refs (to defined queries), or other Query/UnaryOp results
        # may be followed by a bare alias to form a query. We accept any Expr but
        # require the next token to be an unquoted, non-keyword identifier and the
        # token after to be one of: where / return / sort.
        if not isinstance(expr, self._ALIAS_CONTINUATION_TYPES):
            return False
        tok = self._peek()
        if tok.kind is not TokenKind.IDENT:
            return False
        next_tok = self._peek(1)
        return (
            next_tok.kind is TokenKind.KEYWORD
            and next_tok.value in self._QUERY_CLAUSE_KEYWORDS
        )

    def _parse_query_from(self, source_expr: A.Expr) -> A.Query:
        alias_tok = self._advance()
        alias = alias_tok.value
        sources = [A.AliasedSource(expression=source_expr, alias=alias)]
        where_clause: A.WhereClause | None = None
        sort_clauses: list[A.SortByExpr] = []
        return_clause: A.ReturnClause | None = None

        while True:
            if self._match(TokenKind.KEYWORD, "where"):
                where_clause = A.WhereClause(expression=self._parse_expression())
                continue
            if self._match(TokenKind.KEYWORD, "sort"):
                self._expect_keyword("by")
                expr = self._parse_expression()
                direction = "asc"
                if self._match(TokenKind.KEYWORD, "desc"):
                    direction = "desc"
                elif self._match(TokenKind.KEYWORD, "asc"):
                    direction = "asc"
                sort_clauses.append(A.SortByExpr(expression=expr, direction=direction))
                continue
            if self._match(TokenKind.KEYWORD, "return"):
                return_clause = A.ReturnClause(expression=self._parse_expression())
                continue
            break

        return A.Query(
            sources=sources,
            where=where_clause,
            sort=sort_clauses,
            ret=return_clause,
        )

    # --- primary ------------------------------------------------------------

    def _parse_primary(self) -> A.Expr:
        tok = self._peek()
        if tok.kind is TokenKind.PUNCT and tok.value == "(":
            self._advance()
            expr = self._parse_expression()
            self._expect_punct(")")
            return expr
        if tok.kind is TokenKind.PUNCT and tok.value == "{":
            return self._parse_list_literal()
        if tok.kind is TokenKind.PUNCT and tok.value == "[":
            return self._parse_retrieve()
        if tok.kind is TokenKind.KEYWORD and tok.value == "Interval":
            return self._parse_interval_ctor()
        if tok.kind is TokenKind.KEYWORD and tok.value == "true":
            self._advance()
            return A.BoolLit(True)
        if tok.kind is TokenKind.KEYWORD and tok.value == "false":
            self._advance()
            return A.BoolLit(False)
        if tok.kind is TokenKind.KEYWORD and tok.value == "null":
            self._advance()
            return A.NullLit()
        if tok.kind is TokenKind.INTEGER:
            self._advance()
            result: A.Expr = A.IntLit(int(tok.value))
            # Quantity literal: NUMBER STRING
            if self._check(TokenKind.STRING):
                unit = self._advance().value
                result = A.QuantityLit(value=tok.value, unit=unit)
            return result
        if tok.kind is TokenKind.DECIMAL:
            self._advance()
            result_decimal: A.Expr = A.DecimalLit(tok.value)
            if self._check(TokenKind.STRING):
                unit = self._advance().value
                result_decimal = A.QuantityLit(value=tok.value, unit=unit)
            return result_decimal
        if tok.kind is TokenKind.STRING:
            self._advance()
            return A.StringLit(tok.value)
        if tok.kind is TokenKind.DATETIME:
            self._advance()
            return self._make_datetime_literal(tok.value)
        if tok.kind is TokenKind.QUOTED_IDENT:
            self._advance()
            return self._maybe_function_or_ref(tok.value)
        if tok.kind is TokenKind.IDENT:
            self._advance()
            return self._maybe_function_or_ref(tok.value)
        raise CqlParseError(
            f"Unexpected token {tok.value!r} in expression",
            line=tok.line,
            column=tok.column,
        )

    def _maybe_function_or_ref(self, name: str) -> A.Expr:
        # Qualified function call: X.func(...). We only consume the dotted
        # qualifier when it's clearly a library-qualified function call
        # (followed by `(`). Plain `X.field` is left for the postfix loop to
        # turn into a Property node so that alias property access works.
        library_alias: str | None = None
        head = name
        if (
            self._check(TokenKind.PUNCT, ".")
            and self._peek(1).kind in (TokenKind.QUOTED_IDENT, TokenKind.IDENT, TokenKind.KEYWORD)
            and self._peek(2).kind is TokenKind.PUNCT
            and self._peek(2).value == "("
        ):
            self._advance()
            ref_tok = self._advance()
            library_alias = head
            head = ref_tok.value
        # Function call?
        if self._check(TokenKind.PUNCT, "("):
            self._advance()
            args: list[A.Expr] = []
            if not self._check(TokenKind.PUNCT, ")"):
                args.append(self._parse_expression())
                while self._match(TokenKind.PUNCT, ","):
                    args.append(self._parse_expression())
            self._expect_punct(")")
            return A.FunctionCall(name=head, args=args, library=library_alias)
        return A.Ref(name=head, library=library_alias)

    def _parse_list_literal(self) -> A.ListCtor:
        self._expect_punct("{")
        elements: list[A.Expr] = []
        if not self._check(TokenKind.PUNCT, "}"):
            elements.append(self._parse_expression())
            while self._match(TokenKind.PUNCT, ","):
                elements.append(self._parse_expression())
        self._expect_punct("}")
        return A.ListCtor(elements=elements)

    def _parse_interval_ctor(self) -> A.IntervalCtor:
        self._expect_keyword("Interval")
        open_tok = self._advance()
        if open_tok.kind is not TokenKind.PUNCT or open_tok.value not in {"[", "("}:
            raise CqlParseError("Expected '[' or '(' after 'Interval'", line=open_tok.line)
        low_closed = open_tok.value == "["
        low = self._parse_expression()
        self._expect_punct(",")
        high = self._parse_expression()
        close_tok = self._advance()
        if close_tok.kind is not TokenKind.PUNCT or close_tok.value not in {"]", ")"}:
            raise CqlParseError("Expected ']' or ')' to close Interval", line=close_tok.line)
        high_closed = close_tok.value == "]"
        return A.IntervalCtor(low=low, high=high, low_closed=low_closed, high_closed=high_closed)

    def _parse_retrieve(self) -> A.Retrieve:
        self._expect_punct("[")
        data_type_tok = self._advance()
        if data_type_tok.kind not in (TokenKind.IDENT, TokenKind.KEYWORD):
            raise CqlParseError("Expected resource type inside retrieve", line=data_type_tok.line)
        data_type = data_type_tok.value
        code_path: str | None = None
        value_set: str | None = None
        if self._match(TokenKind.PUNCT, ":"):
            # Optional code path is omitted in CQL — the spec defaults it per data model.
            # We treat ``[Encounter: "VS"]`` as the common case (no explicit path).
            vs_tok = self._advance()
            if vs_tok.kind is not TokenKind.QUOTED_IDENT:
                raise CqlParseError(
                    "Expected value set name in retrieve",
                    line=vs_tok.line,
                    column=vs_tok.column,
                )
            value_set = vs_tok.value
        self._expect_punct("]")
        return A.Retrieve(data_type=data_type, code_path=code_path, value_set=value_set)

    # --- helpers ------------------------------------------------------------

    def _make_datetime_literal(self, raw: str) -> A.DateTimeLit:
        body = raw[1:]  # strip leading @
        date_part, _, time_part = body.partition("T")
        date_components = date_part.split("-")
        year = int(date_components[0])
        month = int(date_components[1]) if len(date_components) > 1 else None
        day = int(date_components[2]) if len(date_components) > 2 else None
        hour = minute = second = millisecond = None
        if time_part:
            time_clean = time_part
            ms_part: str | None = None
            if "." in time_clean:
                time_clean, _, ms_part = time_clean.partition(".")
            time_components = time_clean.split(":")
            if len(time_components) > 0 and time_components[0] != "":
                hour = int(time_components[0])
            if len(time_components) > 1:
                minute = int(time_components[1])
            if len(time_components) > 2:
                second = int(time_components[2])
            if ms_part is not None:
                # Take only digits, normalize to milliseconds (3 digits).
                digits = ms_part.rstrip()
                if digits:
                    digits = (digits + "000")[:3]
                    millisecond = int(digits)
        return A.DateTimeLit(
            raw=raw,
            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            second=second,
            millisecond=millisecond,
        )


def parse(tokens: list[Token]) -> A.Library:
    """Parse a token list into an AST :class:`Library` node."""
    return _Parser(tokens).parse_library()
