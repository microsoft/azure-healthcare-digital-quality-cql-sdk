"""AST nodes produced by the CQL parser.

These dataclasses are an intermediate form: the parser emits them; the
:mod:`cql_sdk.compiler.cql_to_elm.translator` consumes them and produces ELM
JSON. They are not part of the public SDK surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --- Type specifiers --------------------------------------------------------


@dataclass(slots=True)
class TypeSpec:
    """Reference to a CQL type. ``argument`` covers ``Interval<DateTime>`` etc."""

    name: str
    argument: TypeSpec | None = None


# --- Expressions ------------------------------------------------------------


class Expr:
    """Base marker for AST expression nodes."""

    __slots__ = ()


@dataclass(slots=True)
class BoolLit(Expr):
    value: bool


@dataclass(slots=True)
class IntLit(Expr):
    value: int


@dataclass(slots=True)
class DecimalLit(Expr):
    text: str  # preserved verbatim so we don't lose precision


@dataclass(slots=True)
class StringLit(Expr):
    value: str


@dataclass(slots=True)
class NullLit(Expr):
    pass


@dataclass(slots=True)
class DateTimeLit(Expr):
    raw: str
    year: int
    month: int | None = None
    day: int | None = None
    hour: int | None = None
    minute: int | None = None
    second: int | None = None
    millisecond: int | None = None


@dataclass(slots=True)
class QuantityLit(Expr):
    value: str
    unit: str


@dataclass(slots=True)
class Ref(Expr):
    """Reference to a named identifier — resolution happens in the translator."""

    name: str
    library: str | None = None  # for ``X.foo`` qualified references


@dataclass(slots=True)
class FunctionCall(Expr):
    name: str
    args: list[Expr] = field(default_factory=list)
    library: str | None = None


@dataclass(slots=True)
class PropertyAccess(Expr):
    source: Expr
    path: str


@dataclass(slots=True)
class UnaryOp(Expr):
    op: str
    operand: Expr


@dataclass(slots=True)
class BinaryOp(Expr):
    op: str
    left: Expr
    right: Expr


@dataclass(slots=True)
class Cast(Expr):
    operand: Expr
    target: TypeSpec


@dataclass(slots=True)
class IntervalCtor(Expr):
    low: Expr
    high: Expr
    low_closed: bool
    high_closed: bool


@dataclass(slots=True)
class DurationOf(Expr):
    """``duration in <precision> of <interval>``."""

    precision: str
    operand: Expr


@dataclass(slots=True)
class ListCtor(Expr):
    elements: list[Expr] = field(default_factory=list)


@dataclass(slots=True)
class Retrieve(Expr):
    data_type: str        # bare ``Encounter``
    code_path: str | None  # e.g. ``type`` or ``code``; None when no terminology filter
    value_set: str | None  # quoted name of a valueset


@dataclass(slots=True)
class WhereClause:
    expression: Expr


@dataclass(slots=True)
class SortByExpr:
    expression: Expr
    direction: str  # "asc" or "desc"


@dataclass(slots=True)
class ReturnClause:
    expression: Expr


@dataclass(slots=True)
class AliasedSource:
    expression: Expr
    alias: str


@dataclass(slots=True)
class Query(Expr):
    sources: list[AliasedSource]
    where: WhereClause | None = None
    sort: list[SortByExpr] = field(default_factory=list)
    ret: ReturnClause | None = None


# --- Library-level declarations --------------------------------------------


@dataclass(slots=True)
class Using:
    name: str
    version: str | None
    uri: str | None = None


@dataclass(slots=True)
class Include:
    name: str
    version: str | None
    alias: str | None


@dataclass(slots=True)
class CodeSystemDef:
    name: str
    uri: str


@dataclass(slots=True)
class ValueSetDef:
    name: str
    uri: str


@dataclass(slots=True)
class CodeDef:
    name: str
    code: str
    code_system: str
    display: str | None


@dataclass(slots=True)
class ParameterDef:
    name: str
    type_specifier: TypeSpec | None
    default: Expr | None


@dataclass(slots=True)
class StatementDef:
    name: str
    expression: Expr


@dataclass(slots=True)
class LibraryIdent:
    id: str
    version: str | None


@dataclass(slots=True)
class Library:
    identifier: LibraryIdent
    usings: list[Using] = field(default_factory=list)
    includes: list[Include] = field(default_factory=list)
    code_systems: list[CodeSystemDef] = field(default_factory=list)
    value_sets: list[ValueSetDef] = field(default_factory=list)
    codes: list[CodeDef] = field(default_factory=list)
    parameters: list[ParameterDef] = field(default_factory=list)
    context: str | None = None
    statements: list[StatementDef] = field(default_factory=list)
