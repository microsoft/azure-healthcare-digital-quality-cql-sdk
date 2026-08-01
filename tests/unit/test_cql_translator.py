import json

import pytest

from cql_sdk.compiler.cql_to_elm import compile_text, translate
from cql_sdk.elm.serialization.loader import load_library_from_string
from tests.fixtures.cql import HEADER_WITH_ALL_DECLS, SAMPLE_MEASURE, TINY_LIBRARY


@pytest.mark.unit
def test_translate_emits_envelope_and_identifier():
    elm = translate(TINY_LIBRARY)
    assert "library" in elm
    assert elm["library"]["identifier"] == {"id": "Tiny", "version": "1"}
    assert elm["library"]["contexts"]["def"] == [{"name": "Patient"}]


@pytest.mark.unit
def test_translate_alias_for_compile_text():
    assert compile_text(TINY_LIBRARY) == translate(TINY_LIBRARY)


@pytest.mark.unit
def test_translate_declarations_round_trip():
    elm = translate(HEADER_WITH_ALL_DECLS)
    lib = elm["library"]
    assert [u["localIdentifier"] for u in lib["usings"]["def"]] == ["FHIR"]
    assert [i["path"] for i in lib["includes"]["def"]] == ["FHIRHelpers"]
    assert [cs["name"] for cs in lib["codeSystems"]["def"]] == ["LOINC"]
    assert [vs["name"] for vs in lib["valueSets"]["def"]] == ["Diabetes"]
    assert [c["name"] for c in lib["codes"]["def"]] == ["HbA1c"]
    assert lib["codes"]["def"][0]["display"] == "Hemoglobin A1c"
    assert lib["parameters"]["def"][0]["name"] == "Measurement Period"


@pytest.mark.unit
def test_translate_assigns_correct_ref_kinds():
    elm = translate(SAMPLE_MEASURE)
    statements = {s["name"]: s for s in elm["library"]["statements"]["def"]}

    initial_pop = statements["Initial Population"]["expression"]
    # Initial Population is "Adult and Diabetes Encounters"-ish; locate the
    # AgeInYearsAt at(start of MP) and assert MP resolves to ParameterRef.
    body = json.dumps(initial_pop)
    assert '"type": "ParameterRef"' in body
    assert '"name": "Measurement Period"' in body

    encounters = statements["Diabetes Encounters"]["expression"]
    body = json.dumps(encounters)
    assert '"type": "Retrieve"' in body
    assert '"type": "ValueSetRef"' in body
    # E.status -> Property over AliasRef
    assert '"type": "AliasRef"' in body
    assert '"path": "status"' in body


@pytest.mark.unit
def test_translated_elm_is_loadable_by_sdk_loader():
    elm = translate(SAMPLE_MEASURE)
    lib = load_library_from_string(json.dumps(elm))
    assert lib.identifier.id == "SampleMeasure"
    assert "Initial Population" in lib.definitions
    assert "Measurement Period" in lib.parameters
    assert "Diabetes" in lib.value_sets


@pytest.mark.unit
def test_translate_quantity_literal_preserves_text():
    elm = translate(SAMPLE_MEASURE)
    numerator = next(
        s for s in elm["library"]["statements"]["def"] if s["name"] == "Numerator"
    )
    body = json.dumps(numerator)
    assert '"type": "Quantity"' in body
    assert '"value": "9.0"' in body
    assert '"unit": "%"' in body


_HDR = "library X version '1'\nusing FHIR version '4.0.1'\ncontext Patient\n"


def _expr(src: str) -> dict:
    elm = translate(_HDR + src)
    return elm["library"]["statements"]["def"][0]["expression"]


@pytest.mark.unit
def test_translate_between_expands_to_and_of_comparisons():
    node = _expr("define A: x between 50 and 74")
    assert node["type"] == "And"
    kinds = [op["type"] for op in node["operand"]]
    assert kinds == ["GreaterOrEqual", "LessOrEqual"]
    assert node["operand"][0]["operand"][1]["value"] == "50"
    assert node["operand"][1]["operand"][1]["value"] == "74"


@pytest.mark.unit
def test_translate_if_and_case():
    if_node = _expr("define A: if x then 'Y' else 'N'")
    assert if_node["type"] == "If"
    assert {"condition", "then", "else"} <= set(if_node)

    case_node = _expr("define A: case when x then 1 else 2 end")
    assert case_node["type"] == "Case"
    assert case_node["caseItem"][0]["when"]["type"] == "ExpressionRef"
    assert case_node["else"]["value"] == "2"


@pytest.mark.unit
def test_translate_difference_and_duration_between():
    diff = _expr("define A: difference in weeks between x and y")
    assert diff["type"] == "DifferenceBetween"
    assert diff["precision"] == "week"
    assert len(diff["operand"]) == 2

    dur = _expr("define A: duration in days between x and y")
    assert dur["type"] == "DurationBetween"
    assert dur["precision"] == "day"


@pytest.mark.unit
def test_translate_exists_and_now_function_forms():
    exists_node = _expr("define A: Exists([Encounter])")
    assert exists_node["type"] == "Exists"
    assert isinstance(exists_node["operand"], dict)  # single operand, not a list

    now_node = _expr("define A: Now()")
    assert now_node == {"type": "Now"}


@pytest.mark.unit
def test_translate_datetime_timezone_offset():
    z = _expr("define A: @2026-01-01T00:00:00Z")
    assert z["timezoneOffset"]["value"] == "0"
    assert z["timezoneOffset"]["valueType"].endswith("Decimal")
    plus = _expr("define A: @2026-06-01T12:30:00+05:30")
    assert plus["timezoneOffset"]["value"] == "5.5"


@pytest.mark.unit
def test_translate_qualified_cast_type_maps_to_fhir_namespace():
    node = _expr("define A: x as FHIR.dateTime")
    assert node["type"] == "As"
    assert node["asType"] == "{http://hl7.org/fhir}dateTime"


@pytest.mark.unit
def test_new_constructs_load_through_sdk_loader():
    src = _HDR + (
        "define A: if Exists([Encounter]) then 'Y' else 'N'\n"
        "define B: case when true then 1 else 0 end\n"
        "define C: @2026-01-01T00:00:00Z\n"
    )
    lib = load_library_from_string(json.dumps(translate(src)))
    assert {"A", "B", "C"} <= set(lib.definitions)
