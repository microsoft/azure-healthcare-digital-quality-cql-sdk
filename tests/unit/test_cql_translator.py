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
