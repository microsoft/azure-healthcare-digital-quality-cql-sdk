import pytest

from cql_sdk.compiler.cql_to_elm import ast as A
from cql_sdk.compiler.cql_to_elm.lexer import tokenize
from cql_sdk.compiler.cql_to_elm.parser import parse
from tests.fixtures.cql import HEADER_WITH_ALL_DECLS, SAMPLE_MEASURE, TINY_LIBRARY


@pytest.mark.unit
def test_parse_minimal_library():
    lib = parse(tokenize(TINY_LIBRARY))
    assert lib.identifier.id == "Tiny"
    assert lib.identifier.version == "1"
    assert lib.context == "Patient"
    assert len(lib.statements) == 1
    stmt = lib.statements[0]
    assert stmt.name == "One Plus Two"
    assert isinstance(stmt.expression, A.BinaryOp)
    assert stmt.expression.op == "+"
    assert isinstance(stmt.expression.left, A.IntLit) and stmt.expression.left.value == 1
    assert isinstance(stmt.expression.right, A.IntLit) and stmt.expression.right.value == 2


@pytest.mark.unit
def test_parse_all_declaration_kinds():
    lib = parse(tokenize(HEADER_WITH_ALL_DECLS))
    assert lib.identifier.id == "Header"
    assert [u.name for u in lib.usings] == ["FHIR"]
    assert [i.name for i in lib.includes] == ["FHIRHelpers"]
    assert lib.includes[0].alias == "FHIRHelpers"
    assert [c.name for c in lib.code_systems] == ["LOINC"]
    assert [v.name for v in lib.value_sets] == ["Diabetes"]
    assert [c.name for c in lib.codes] == ["HbA1c"]
    assert lib.codes[0].code == "4548-4"
    assert lib.codes[0].display == "Hemoglobin A1c"
    assert [p.name for p in lib.parameters] == ["Measurement Period"]
    assert lib.parameters[0].type_specifier is not None
    assert lib.parameters[0].type_specifier.name == "Interval"
    assert lib.parameters[0].type_specifier.argument.name == "DateTime"


@pytest.mark.unit
def test_parse_retrieve_with_alias_and_clauses():
    lib = parse(tokenize(SAMPLE_MEASURE))
    encounters = next(s for s in lib.statements if s.name == "Diabetes Encounters")
    assert isinstance(encounters.expression, A.Query)
    query = encounters.expression
    assert len(query.sources) == 1
    assert isinstance(query.sources[0].expression, A.Retrieve)
    assert query.sources[0].expression.data_type == "Encounter"
    assert query.sources[0].expression.value_set == "Diabetes"
    assert query.sources[0].alias == "E"
    assert query.where is not None


@pytest.mark.unit
def test_parse_property_access_on_alias():
    lib = parse(tokenize(SAMPLE_MEASURE))
    encounters = next(s for s in lib.statements if s.name == "Diabetes Encounters")
    where = encounters.expression.where.expression
    # E.status = 'finished' AND E.period during "Measurement Period"
    assert isinstance(where, A.BinaryOp) and where.op == "and"
    left = where.left
    assert isinstance(left, A.BinaryOp) and left.op == "="
    assert isinstance(left.left, A.PropertyAccess)
    assert left.left.path == "status"
    assert isinstance(left.left.source, A.Ref)
    assert left.left.source.name == "E"


@pytest.mark.unit
def test_parse_quantity_literal():
    lib = parse(tokenize(SAMPLE_MEASURE))
    numerator = next(s for s in lib.statements if s.name == "Numerator")
    # The first comparison inside the exists is "O.value as Quantity > 9.0 '%'".
    # Drill down: exists -> Query -> where -> And -> Greater(Cast(O.value, Quantity), QuantityLit)
    exists_expr = numerator.expression
    assert isinstance(exists_expr, A.UnaryOp) and exists_expr.op == "exists"
    query = exists_expr.operand
    assert isinstance(query, A.Query)
    where = query.where.expression
    assert isinstance(where, A.BinaryOp) and where.op == "and"
    greater = where.left
    assert isinstance(greater, A.BinaryOp) and greater.op == ">"
    assert isinstance(greater.right, A.QuantityLit)
    assert greater.right.value == "9.0"
    assert greater.right.unit == "%"
