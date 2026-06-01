"""AST → ELM JSON translator.

Emits a top-level ``{"library": {...}}`` envelope compatible with
:func:`cql_sdk.elm.serialization.loader.load_library_from_string`. The
output deliberately omits ``resultTypeName`` and other annotation fields —
the interpreter does not consume them, and inferring them faithfully would
require type-resolving the entire FHIR profile graph.
"""

from __future__ import annotations

from typing import Any

from cql_sdk.compiler.cql_to_elm import ast as A
from cql_sdk.compiler.cql_to_elm.errors import CqlTranslationError

_ELM_PRIMITIVE = "{urn:hl7-org:elm-types:r1}"
_FHIR_NS = "{http://hl7.org/fhir}"


_BINARY_OP_TO_ELM = {
    "and": "And",
    "or": "Or",
    "=": "Equal",
    "!=": "NotEqual",
    "~": "Equivalent",
    "<": "Less",
    "<=": "LessOrEqual",
    ">": "Greater",
    ">=": "GreaterOrEqual",
    "+": "Add",
    "-": "Subtract",
    "*": "Multiply",
    "/": "Divide",
    "in": "In",
    "during": "IncludedIn",
    "overlaps": "Overlaps",
    "before": "Before",
    "after": "After",
    "ends during": "EndsIncludedIn",
    "starts during": "StartsIncludedIn",
}


_UNARY_OP_TO_ELM = {
    "not": "Not",
    "exists": "Exists",
    "-": "Negate",
    "start of": "Start",
    "end of": "End",
    "date from": "DateFrom",
    "singleton from": "SingletonFrom",
    "flatten": "Flatten",
    "is null": "IsNull",
}


class _SymbolTable:
    """Resolves a CQL identifier to its ELM reference kind."""

    def __init__(self, library: A.Library) -> None:
        self.parameters = {p.name for p in library.parameters}
        self.value_sets = {v.name for v in library.value_sets}
        self.code_systems = {c.name for c in library.code_systems}
        self.codes = {c.name for c in library.codes}
        self.statements = {s.name for s in library.statements}
        self.includes = {(i.alias or i.name) for i in library.includes}
        self.alias_stack: list[set[str]] = []

    def push_aliases(self, aliases: set[str]) -> None:
        self.alias_stack.append(aliases)

    def pop_aliases(self) -> None:
        self.alias_stack.pop()

    def is_alias(self, name: str) -> bool:
        return any(name in scope for scope in self.alias_stack)

    def kind_for(self, name: str) -> str:
        if self.is_alias(name):
            return "AliasRef"
        if name in self.parameters:
            return "ParameterRef"
        if name in self.value_sets:
            return "ValueSetRef"
        if name in self.codes:
            return "CodeRef"
        if name in self.code_systems:
            return "CodeSystemRef"
        # Anything else is assumed to be a same-library statement reference.
        return "ExpressionRef"


def translate_library(library: A.Library) -> dict[str, Any]:
    """Translate a parsed CQL AST into an ELM JSON document."""
    symbols = _SymbolTable(library)
    using_uris = {u.name: _model_uri(u.name) for u in library.usings}

    return {
        "library": {
            "identifier": {
                "id": library.identifier.id,
                **({"version": library.identifier.version} if library.identifier.version else {}),
            },
            "schemaIdentifier": {"id": "urn:hl7-org:elm", "version": "r1"},
            "usings": {"def": [_translate_using(u) for u in library.usings]},
            "includes": {"def": [_translate_include(i) for i in library.includes]},
            "codeSystems": {"def": [_translate_codesystem(c) for c in library.code_systems]},
            "valueSets": {"def": [_translate_valueset(v) for v in library.value_sets]},
            "codes": {"def": [_translate_code(c) for c in library.codes]},
            "parameters": {"def": [_translate_parameter(p, symbols) for p in library.parameters]},
            "contexts": {"def": ([{"name": library.context}] if library.context else [])},
            "statements": {
                "def": [
                    _translate_statement(s, symbols, library.context, using_uris)
                    for s in library.statements
                ]
            },
        }
    }


# --- library-level translators --------------------------------------------


def _model_uri(name: str) -> str:
    if name in ("FHIR", "FHIRHelpers"):
        return "http://hl7.org/fhir"
    if name == "QUICK":
        return "http://hl7.org/fhir"
    return f"urn:hl7-org:elm-using:{name}"


def _translate_using(u: A.Using) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "localIdentifier": u.name,
        "uri": _model_uri(u.name),
    }
    if u.version:
        entry["version"] = u.version
    return entry


def _translate_include(i: A.Include) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "localIdentifier": i.alias or i.name,
        "path": i.name,
    }
    if i.version:
        entry["version"] = i.version
    return entry


def _translate_codesystem(c: A.CodeSystemDef) -> dict[str, Any]:
    return {
        "name": c.name,
        "id": c.uri,
        "accessLevel": "Public",
    }


def _translate_valueset(v: A.ValueSetDef) -> dict[str, Any]:
    return {
        "name": v.name,
        "id": v.uri,
        "accessLevel": "Public",
    }


def _translate_code(c: A.CodeDef) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "name": c.name,
        "id": c.code,
        "codeSystem": {"name": c.code_system},
        "accessLevel": "Public",
    }
    if c.display:
        entry["display"] = c.display
    return entry


def _translate_parameter(p: A.ParameterDef, symbols: _SymbolTable) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "name": p.name,
        "accessLevel": "Public",
    }
    if p.type_specifier:
        entry["parameterTypeSpecifier"] = _translate_type_specifier(p.type_specifier)
    if p.default is not None:
        entry["default"] = _translate_expression(p.default, symbols)
    return entry


def _translate_statement(
    s: A.StatementDef,
    symbols: _SymbolTable,
    context: str | None,
    using_uris: dict[str, str],
) -> dict[str, Any]:
    return {
        "name": s.name,
        "context": context or "Patient",
        "accessLevel": "Public",
        "expression": _translate_expression(s.expression, symbols, using_uris=using_uris),
    }


# --- type specifiers -------------------------------------------------------


def _translate_type_specifier(ts: A.TypeSpec) -> dict[str, Any]:
    if ts.argument is not None:
        return {
            "type": "IntervalTypeSpecifier" if ts.name == "Interval" else "ListTypeSpecifier",
            "pointType": _translate_type_specifier(ts.argument)
            if ts.name == "Interval"
            else None,
            "elementType": _translate_type_specifier(ts.argument)
            if ts.name == "List"
            else None,
        }
    return {
        "type": "NamedTypeSpecifier",
        "name": _qualify_type(ts.name),
    }


def _qualify_type(name: str) -> str:
    """Wrap a primitive CQL type name in the ELM URN namespace."""
    primitives = {
        "Boolean", "Integer", "Decimal", "String", "Quantity", "Ratio",
        "DateTime", "Date", "Time", "Code", "Concept", "Any",
    }
    if name in primitives:
        return f"{_ELM_PRIMITIVE}{name}"
    return f"{_FHIR_NS}{name}"


def _normalize_precision(unit: str) -> str:
    """Normalize a CQL duration unit identifier to an ELM precision label."""
    table = {
        "year": "year", "years": "year",
        "month": "month", "months": "month",
        "week": "week", "weeks": "week",
        "day": "day", "days": "day",
        "hour": "hour", "hours": "hour",
        "minute": "minute", "minutes": "minute",
        "second": "second", "seconds": "second",
        "millisecond": "millisecond", "milliseconds": "millisecond",
    }
    return table.get(unit, unit)


# --- expression dispatch ---------------------------------------------------


def _translate_expression(
    expr: A.Expr,
    symbols: _SymbolTable,
    *,
    using_uris: dict[str, str] | None = None,
) -> dict[str, Any]:
    using_uris = using_uris or {}

    if isinstance(expr, A.BoolLit):
        return {
            "type": "Literal",
            "value": "true" if expr.value else "false",
            "valueType": f"{_ELM_PRIMITIVE}Boolean",
        }
    if isinstance(expr, A.IntLit):
        return {
            "type": "Literal",
            "value": str(expr.value),
            "valueType": f"{_ELM_PRIMITIVE}Integer",
        }
    if isinstance(expr, A.DecimalLit):
        return {
            "type": "Literal",
            "value": expr.text,
            "valueType": f"{_ELM_PRIMITIVE}Decimal",
        }
    if isinstance(expr, A.StringLit):
        return {
            "type": "Literal",
            "value": expr.value,
            "valueType": f"{_ELM_PRIMITIVE}String",
        }
    if isinstance(expr, A.NullLit):
        return {"type": "Null"}
    if isinstance(expr, A.DateTimeLit):
        return _translate_datetime(expr)
    if isinstance(expr, A.QuantityLit):
        # ELM represents Quantity values numerically, but we preserve the
        # decimal text to avoid float drift.
        return {"type": "Quantity", "value": expr.value, "unit": expr.unit}
    if isinstance(expr, A.Ref):
        return _translate_ref(expr, symbols)
    if isinstance(expr, A.FunctionCall):
        return _translate_function_call(expr, symbols, using_uris)
    if isinstance(expr, A.PropertyAccess):
        # Recognize `LibraryAlias.identifier` member access against an
        # included library and emit it as a qualified ExpressionRef so the
        # runtime can dispatch to codes/value sets/statements directly.
        # `Global` is special-cased because measures conventionally reference
        # it even without an explicit `include` statement; the runtime
        # aliases it to FHIRHelpers.
        src = expr.source
        if (
            isinstance(src, A.Ref)
            and src.library is None
            and src.name
            not in (
                symbols.parameters
                | symbols.value_sets
                | symbols.codes
                | symbols.code_systems
                | symbols.statements
            )
            and (src.name in symbols.includes or src.name == "Global")
        ):
            return {
                "type": "ExpressionRef",
                "name": expr.path,
                "libraryName": src.name,
            }
        return {
            "type": "Property",
            "source": _translate_expression(expr.source, symbols, using_uris=using_uris),
            "path": expr.path,
        }
    if isinstance(expr, A.UnaryOp):
        return _translate_unary(expr, symbols, using_uris)
    if isinstance(expr, A.BinaryOp):
        return _translate_binary(expr, symbols, using_uris)
    if isinstance(expr, A.Cast):
        return {
            "type": "As",
            "operand": _translate_expression(expr.operand, symbols, using_uris=using_uris),
            "asType": _qualify_type(expr.target.name),
        }
    if isinstance(expr, A.IntervalCtor):
        return {
            "type": "Interval",
            "low": _translate_expression(expr.low, symbols, using_uris=using_uris),
            "high": _translate_expression(expr.high, symbols, using_uris=using_uris),
            "lowClosed": expr.low_closed,
            "highClosed": expr.high_closed,
        }
    if isinstance(expr, A.DurationOf):
        operand = _translate_expression(expr.operand, symbols, using_uris=using_uris)
        return {
            "type": "DurationBetween",
            "precision": _normalize_precision(expr.precision),
            "operand": [
                {"type": "Start", "operand": operand},
                {"type": "End", "operand": operand},
            ],
        }
    if isinstance(expr, A.ListCtor):
        return {
            "type": "List",
            "element": [
                _translate_expression(e, symbols, using_uris=using_uris) for e in expr.elements
            ],
        }
    if isinstance(expr, A.Retrieve):
        return _translate_retrieve(expr, symbols)
    if isinstance(expr, A.Query):
        return _translate_query(expr, symbols, using_uris)

    raise CqlTranslationError(f"Unsupported AST node: {type(expr).__name__}")


def _translate_datetime(d: A.DateTimeLit) -> dict[str, Any]:
    is_date_only = d.hour is None and d.minute is None and d.second is None
    out: dict[str, Any] = {
        "type": "Date" if is_date_only else "DateTime",
    }

    def _lit(value: int) -> dict[str, Any]:
        return {
            "type": "Literal",
            "value": str(value),
            "valueType": f"{_ELM_PRIMITIVE}Integer",
        }

    out["year"] = _lit(d.year)
    if d.month is not None:
        out["month"] = _lit(d.month)
    if d.day is not None:
        out["day"] = _lit(d.day)
    if out["type"] == "DateTime":
        if d.hour is not None:
            out["hour"] = _lit(d.hour)
        if d.minute is not None:
            out["minute"] = _lit(d.minute)
        if d.second is not None:
            out["second"] = _lit(d.second)
        if d.millisecond is not None:
            out["millisecond"] = _lit(d.millisecond)
    return out


def _translate_ref(ref: A.Ref, symbols: _SymbolTable) -> dict[str, Any]:
    kind = symbols.kind_for(ref.name)
    entry: dict[str, Any] = {"type": kind, "name": ref.name}
    if ref.library:
        entry["libraryName"] = ref.library
    return entry


def _translate_function_call(
    call: A.FunctionCall,
    symbols: _SymbolTable,
    using_uris: dict[str, str],
) -> dict[str, Any]:
    # The parser is intentionally ambiguous about `X.method(...)`: it always
    # emits this as `FunctionCall(name="method", library="X")`. At translation
    # time we can disambiguate: if `X` is not a known included library (or the
    # special `Global` alias), it's actually a query alias / parameter / etc.
    # and the call is fluent — rewrite to put the receiver in front.
    library = call.library
    args = list(call.args)
    if library and library not in symbols.includes and library != "Global":
        args.insert(0, A.Ref(name=library, library=None))
        library = None

    operands = [
        _translate_expression(arg, symbols, using_uris=using_uris) for arg in args
    ]

    # Recognize a handful of built-ins that have first-class ELM types.
    builtin_map = {
        "Last": "Last",
        "First": "First",
        "Count": "Count",
        "Length": "Length",
        "ToConcept": "ToConcept",
        "Coalesce": "Coalesce",
        "AgeInYears": "CalculateAge",
        "AgeInYearsAt": "CalculateAgeAt",
    }
    if library is None and call.name in builtin_map:
        elm_type = builtin_map[call.name]
        # Operators that take a single source expression use "source", others use "operand".
        if elm_type in ("Last", "First", "Count", "Length"):
            return {"type": elm_type, "source": operands[0] if operands else {"type": "Null"}}
        return {"type": elm_type, "operand": operands}

    entry: dict[str, Any] = {
        "type": "FunctionRef",
        "name": call.name,
        "operand": operands,
    }
    if library:
        entry["libraryName"] = library
    return entry


def _translate_unary(
    op: A.UnaryOp,
    symbols: _SymbolTable,
    using_uris: dict[str, str],
) -> dict[str, Any]:
    operand = _translate_expression(op.operand, symbols, using_uris=using_uris)
    if op.op == "is not null":
        return {
            "type": "Not",
            "operand": {"type": "IsNull", "operand": operand},
        }
    elm_name = _UNARY_OP_TO_ELM.get(op.op)
    if not elm_name:
        raise CqlTranslationError(f"Unsupported unary operator: {op.op!r}")
    return {"type": elm_name, "operand": operand}


def _translate_binary(
    op: A.BinaryOp,
    symbols: _SymbolTable,
    using_uris: dict[str, str],
) -> dict[str, Any]:
    elm_name = _BINARY_OP_TO_ELM.get(op.op)
    if not elm_name:
        raise CqlTranslationError(f"Unsupported binary operator: {op.op!r}")
    return {
        "type": elm_name,
        "operand": [
            _translate_expression(op.left, symbols, using_uris=using_uris),
            _translate_expression(op.right, symbols, using_uris=using_uris),
        ],
    }


def _translate_retrieve(r: A.Retrieve, symbols: _SymbolTable) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "type": "Retrieve",
        "dataType": f"{_FHIR_NS}{r.data_type}",
        "templateId": f"http://hl7.org/fhir/StructureDefinition/{r.data_type}",
    }
    if r.value_set:
        kind = symbols.kind_for(r.value_set)
        # Default code property per the QICore profile for the common resources.
        default_code_path = {
            "Encounter": "type",
            "Condition": "code",
            "Observation": "code",
            "MedicationRequest": "medication",
            "Procedure": "code",
            "Immunization": "vaccineCode",
        }.get(r.data_type, "code")
        if kind == "CodeRef":
            entry["codes"] = {"type": "ToList", "operand": {"type": "CodeRef", "name": r.value_set}}
        elif kind == "ConceptRef":
            entry["codes"] = {"type": "ConceptRef", "name": r.value_set}
        else:
            entry["codes"] = {"type": "ValueSetRef", "name": r.value_set}
        entry["codeProperty"] = r.code_path or default_code_path
    return entry


def _translate_query(
    query: A.Query,
    symbols: _SymbolTable,
    using_uris: dict[str, str],
) -> dict[str, Any]:
    aliases = {src.alias for src in query.sources}
    symbols.push_aliases(aliases)

    def _tx(expr: A.Expr) -> dict[str, Any]:
        return _translate_expression(expr, symbols, using_uris=using_uris)

    try:
        source_defs = [
            {
                "type": "AliasedQuerySource",
                "alias": src.alias,
                "expression": _tx(src.expression),
            }
            for src in query.sources
        ]
        entry: dict[str, Any] = {
            "type": "Query",
            "source": source_defs,
        }
        if query.where is not None:
            entry["where"] = _tx(query.where.expression)
        if query.sort:
            entry["sort"] = {
                "by": [
                    {
                        "type": "ByExpression",
                        "direction": s.direction,
                        "expression": _tx(s.expression),
                    }
                    for s in query.sort
                ]
            }
        if query.ret is not None:
            entry["return"] = {"expression": _tx(query.ret.expression)}
        return entry
    finally:
        symbols.pop_aliases()
