"""Tests for the DQM (FHIR/QI-Core) measure evaluation layer and the
interpreter features it depends on (set operations, value-set membership,
user-defined function parameter binding, and query with/without
relationships).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cql_sdk.abstractions.terminology import Code
from cql_sdk.dqm import MeasurePackage
from cql_sdk.elm.serialization.loader import load_library_from_string
from cql_sdk.fhir.terminology import InMemoryTerminology
from cql_sdk.invocation.toolkit import InvocationToolkit
from cql_sdk.runtime.context import RuntimeContext

S = "{urn:hl7-org:elm-types:r1}"
FHIR = "{http://hl7.org/fhir}"


# --- ELM builders ---------------------------------------------------------


def lit(value: Any, type_name: str) -> dict[str, Any]:
    return {"type": "Literal", "value": str(value), "valueType": f"{S}{type_name}"}


def integer(v: int) -> dict[str, Any]:
    return lit(v, "Integer")


def string(v: str) -> dict[str, Any]:
    return lit(v, "String")


def list_expr(*elements: dict[str, Any]) -> dict[str, Any]:
    return {"type": "List", "element": list(elements)}


def vsref(name: str) -> dict[str, Any]:
    return {"type": "ValueSetRef", "name": name}


def retrieve(data_type: str, value_set: str | None = None, code_property: str | None = None):
    node: dict[str, Any] = {"type": "Retrieve", "dataType": f"{FHIR}{data_type}"}
    if value_set:
        node["codes"] = vsref(value_set)
    if code_property:
        node["codeProperty"] = code_property
    return node


def prop(scope: str, path: str) -> dict[str, Any]:
    return {"type": "Property", "scope": scope, "path": path}


def alias_ref(name: str) -> dict[str, Any]:
    return {"type": "AliasRef", "name": name}


def exists(operand: dict[str, Any]) -> dict[str, Any]:
    return {"type": "Exists", "operand": operand}


def expr_ref(name: str, library: str | None = None) -> dict[str, Any]:
    node: dict[str, Any] = {"type": "ExpressionRef", "name": name}
    if library:
        node["libraryName"] = library
    return node


def func_ref(name: str, operands: list[dict[str, Any]], library: str | None = None):
    node: dict[str, Any] = {"type": "FunctionRef", "name": name, "operand": operands}
    if library:
        node["libraryName"] = library
    return node


def make_library(
    lib_id: str,
    statements: list[dict[str, Any]],
    *,
    includes: list[dict[str, Any]] | None = None,
    value_sets: list[dict[str, Any]] | None = None,
    parameters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "library": {
            "identifier": {"id": lib_id, "version": "1.0.0"},
            "usings": {
                "def": [
                    {"localIdentifier": "System", "uri": "urn:hl7-org:elm-types:r1"},
                    {"localIdentifier": "FHIR", "uri": "http://hl7.org/fhir", "version": "4.0.1"},
                ]
            },
            "includes": {"def": includes or []},
            "valueSets": {"def": value_sets or []},
            "parameters": {"def": parameters or []},
            "statements": {"def": statements},
        }
    }


def define(name: str, expression: dict[str, Any], operands: list[str] | None = None):
    stmt: dict[str, Any] = {"name": name, "context": "Patient", "expression": expression}
    if operands is not None:
        stmt["operand"] = [{"name": o} for o in operands]
    return stmt


def eval_expr(
    expression: dict[str, Any],
    *,
    bundle: dict[str, Any] | None = None,
    terminology: Any | None = None,
    extra_libraries: list[dict[str, Any]] | None = None,
    value_sets: list[dict[str, Any]] | None = None,
    includes: list[dict[str, Any]] | None = None,
) -> Any:
    toolkit = InvocationToolkit()
    for lib in extra_libraries or []:
        toolkit.register(load_library_from_string(json.dumps(lib)))
    main = make_library(
        "Main",
        [define("Result", expression)],
        value_sets=value_sets,
        includes=includes,
    )
    toolkit.register(load_library_from_string(json.dumps(main)))
    ctx = RuntimeContext.default()
    if bundle is not None:
        from cql_sdk.dqm.package import QICoreDataSource

        ds = QICoreDataSource(bundle)
        ctx.data_source = ds
        ctx.subject = ds.subject
    ctx.terminology = terminology
    return toolkit.invoke(library_identifier="Main", definition="Result", context=ctx)


# --- interpreter: set operations ------------------------------------------


def test_union_distinct():
    result = eval_expr(
        {"type": "Union", "operand": [list_expr(integer(1), integer(2)), list_expr(integer(2), integer(3))]}
    )
    assert result == [1, 2, 3]


def test_except():
    result = eval_expr(
        {"type": "Except", "operand": [list_expr(integer(1), integer(2), integer(3)), list_expr(integer(2))]}
    )
    assert result == [1, 3]


def test_intersect():
    result = eval_expr(
        {"type": "Intersect", "operand": [list_expr(integer(1), integer(2), integer(3)), list_expr(integer(2), integer(4))]}
    )
    assert result == [2]


# --- interpreter: value-set membership ------------------------------------


def test_in_value_set_true_and_false():
    term = InMemoryTerminology({"urn:oid:vital": [Code(code="8480-6")]})
    value_sets = [{"name": "Vital Sign", "id": "urn:oid:vital"}]
    hit = eval_expr(
        {"type": "InValueSet", "code": string("8480-6"), "valueset": {"name": "Vital Sign"}},
        terminology=term,
        value_sets=value_sets,
    )
    miss = eval_expr(
        {"type": "InValueSet", "code": string("9999-9"), "valueset": {"name": "Vital Sign"}},
        terminology=term,
        value_sets=value_sets,
    )
    assert hit is True
    assert miss is False


# --- interpreter: user function parameter binding -------------------------


def test_same_library_function_parameter_binding():
    lib = make_library(
        "Main",
        [
            define(
                "double",
                {"type": "Multiply", "operand": [{"type": "OperandRef", "name": "x"}, integer(2)]},
                operands=["x"],
            ),
            define("Result", func_ref("double", [integer(21)])),
        ],
    )
    toolkit = InvocationToolkit()
    toolkit.register(load_library_from_string(json.dumps(lib)))
    result = toolkit.invoke(
        library_identifier="Main", definition="Result", context=RuntimeContext.default()
    )
    assert result == 42


def test_cross_library_function_parameter_binding():
    common = make_library(
        "Common",
        [
            define(
                "triple",
                {"type": "Multiply", "operand": [{"type": "OperandRef", "name": "x"}, integer(3)]},
                operands=["x"],
            )
        ],
    )
    result = eval_expr(
        func_ref("triple", [integer(4)], library="Common"),
        extra_libraries=[common],
        includes=[{"localIdentifier": "Common", "path": "Common", "version": "1.0.0"}],
    )
    assert result == 12


# --- interpreter: query with / without ------------------------------------


def test_query_without_relationship():
    query = {
        "type": "Query",
        "source": [{"alias": "E", "expression": list_expr(integer(1), integer(2), integer(3))}],
        "relationship": [
            {
                "type": "Without",
                "alias": "C",
                "expression": list_expr(integer(2)),
                "suchThat": {"type": "Equal", "operand": [alias_ref("E"), alias_ref("C")]},
            }
        ],
    }
    assert eval_expr(query) == [1, 3]


def test_query_with_relationship():
    query = {
        "type": "Query",
        "source": [{"alias": "E", "expression": list_expr(integer(1), integer(2), integer(3))}],
        "relationship": [
            {
                "type": "With",
                "alias": "C",
                "expression": list_expr(integer(2), integer(3)),
                "suchThat": {"type": "Equal", "operand": [alias_ref("E"), alias_ref("C")]},
            }
        ],
    }
    assert eval_expr(query) == [2, 3]


# --- integration: measure package (boolean / patient basis) ---------------


def _common_library() -> dict[str, Any]:
    """A dependency library with a fluent-style function and a union retrieve."""
    finished_body = {
        "type": "Query",
        "source": [{"alias": "E", "expression": {"type": "OperandRef", "name": "encounters"}}],
        "where": {"type": "Equal", "operand": [prop("E", "status"), string("finished")]},
    }
    qualifying = func_ref(
        "finished",
        [
            {
                "type": "Union",
                "operand": [
                    retrieve("Encounter", "Office Visit", "type"),
                    retrieve("Encounter", "Home Visit", "type"),
                ],
            }
        ],
    )
    return make_library(
        "Common",
        [
            define("finished", finished_body, operands=["encounters"]),
            define("Qualifying Encounters", qualifying),
        ],
        value_sets=[
            {"name": "Office Visit", "id": "urn:oid:office"},
            {"name": "Home Visit", "id": "urn:oid:home"},
        ],
    )


def _boolean_measure_library() -> dict[str, Any]:
    age_ge_18 = {
        "type": "GreaterOrEqual",
        "operand": [
            {
                "type": "CalculateAgeAt",
                "precision": "Year",
                "operand": [{"type": "End", "operand": {"type": "ParameterRef", "name": "Measurement Period"}}],
            },
            integer(18),
        ],
    }
    initial_population = {
        "type": "And",
        "operand": [age_ge_18, exists(expr_ref("Qualifying Encounters", "Common"))],
    }
    controlled = {
        "type": "Query",
        "source": [{"alias": "O", "expression": retrieve("Observation", "Vital Sign", "code")}],
        "where": {
            "type": "And",
            "operand": [
                {"type": "InValueSet", "code": prop("O", "code"), "valueset": {"name": "Vital Sign"}},
                {
                    "type": "Less",
                    "operand": [
                        {"type": "As", "operand": prop("O", "value"), "asType": f"{FHIR}Quantity"},
                        {"type": "Quantity", "value": 140, "unit": "mm[Hg]"},
                    ],
                },
            ],
        },
    }
    return make_library(
        "MeasureLib",
        [
            define("Initial Population", initial_population),
            define("Denominator", expr_ref("Initial Population")),
            define(
                "Denominator Exclusions",
                exists(retrieve("Condition", "Excluded Condition", "code")),
            ),
            define("Controlled Observations", controlled),
            define("Numerator", exists(expr_ref("Controlled Observations"))),
            define("SDE Sex", prop_patient_gender()),
        ],
        includes=[{"localIdentifier": "Common", "path": "Common", "version": "1.0.0"}],
        value_sets=[
            {"name": "Excluded Condition", "id": "urn:oid:excl"},
            {"name": "Vital Sign", "id": "urn:oid:vital"},
        ],
        parameters=[{"name": "Measurement Period"}],
    )


def prop_patient_gender() -> dict[str, Any]:
    # Patient.gender via ExpressionRef fallback is awkward; use a Null so the
    # SDE simply evaluates without error in this fixture.
    return {"type": "Null"}


def _boolean_measure_resource() -> dict[str, Any]:
    def population(code: str, expression: str) -> dict[str, Any]:
        return {
            "code": {"coding": [{"code": code}]},
            "criteria": {"language": "text/cql-identifier", "expression": expression},
        }

    return {
        "resourceType": "Measure",
        "url": "http://example.org/Measure/DemoBoolean",
        "name": "DemoBoolean",
        "version": "1.0.0",
        "library": ["http://example.org/Library/MeasureLib"],
        "scoring": {"coding": [{"code": "proportion"}]},
        "improvementNotation": {"coding": [{"code": "increase"}]},
        "group": [
            {
                "id": "Group_1",
                "extension": [
                    {
                        "url": "http://hl7.org/fhir/us/cqfmeasures/StructureDefinition/cqfm-populationBasis",
                        "valueCode": "boolean",
                    }
                ],
                "population": [
                    population("initial-population", "Initial Population"),
                    population("denominator", "Denominator"),
                    population("denominator-exclusion", "Denominator Exclusions"),
                    population("numerator", "Numerator"),
                ],
            }
        ],
        "supplementalData": [
            {"id": "sde-sex", "criteria": {"expression": "SDE Sex"}}
        ],
    }


def _value_set_resource(url: str, codes: list[str]) -> dict[str, Any]:
    return {
        "resourceType": "ValueSet",
        "url": url,
        "expansion": {"contains": [{"code": c} for c in codes]},
    }


def _write_package(root: Path, measure: dict[str, Any], libraries: list[dict[str, Any]], value_sets: list[dict[str, Any]]) -> Path:
    (root / "libraries").mkdir(parents=True, exist_ok=True)
    (root / "valuesets").mkdir(parents=True, exist_ok=True)
    (root / "measure.json").write_text(json.dumps(measure), encoding="utf-8")
    for lib in libraries:
        name = lib["library"]["identifier"]["id"]
        (root / "libraries" / f"{name}.json").write_text(json.dumps(lib), encoding="utf-8")
    for i, vs in enumerate(value_sets):
        (root / "valuesets" / f"vs_{i}.json").write_text(json.dumps(vs), encoding="utf-8")
    return root


def _encounter(eid: str, type_code: str, status: str) -> dict[str, Any]:
    return {
        "resourceType": "Encounter",
        "id": eid,
        "status": status,
        "type": [{"coding": [{"code": type_code}]}],
        "period": {"start": "2026-03-01", "end": "2026-03-02"},
    }


def _observation(oid: str, code: str, value: float) -> dict[str, Any]:
    return {
        "resourceType": "Observation",
        "id": oid,
        "status": "final",
        "code": {"coding": [{"system": "http://loinc.org", "code": code}]},
        "valueQuantity": {"value": value, "unit": "mm[Hg]", "code": "mm[Hg]"},
    }


def _boolean_package(tmp_path: Path) -> MeasurePackage:
    root = _write_package(
        tmp_path / "boolean_pkg",
        _boolean_measure_resource(),
        [_common_library(), _boolean_measure_library()],
        [
            _value_set_resource("urn:oid:office", ["office"]),
            _value_set_resource("urn:oid:home", ["home"]),
            _value_set_resource("urn:oid:excl", ["excl-code"]),
            _value_set_resource("urn:oid:vital", ["8480-6"]),
        ],
    )
    return MeasurePackage.load(root)


def test_boolean_measure_numerator(tmp_path: Path):
    package = _boolean_package(tmp_path)
    bundle = {
        "resourceType": "Bundle",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "pA", "birthDate": "1980-01-01"}},
            {"resource": _encounter("e1", "office", "finished")},
            {"resource": _observation("o1", "8480-6", 120)},
        ],
    }
    result = package.evaluate(bundle, period=("2026-01-01", "2027-01-01"))
    group = result.primary_group
    assert group is not None
    assert group.population("initial-population").in_population is True
    assert group.population("numerator").in_population is True
    assert group.numerator_count == 1
    assert group.denominator_count == 1
    assert group.measure_score == 1.0
    assert result.errors == {}


def test_boolean_measure_in_denominator_not_numerator(tmp_path: Path):
    package = _boolean_package(tmp_path)
    bundle = {
        "resourceType": "Bundle",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "pB", "birthDate": "1980-01-01"}},
            {"resource": _encounter("e1", "office", "finished")},
            {"resource": _observation("o1", "8480-6", 160)},  # uncontrolled
        ],
    }
    result = package.evaluate(bundle, period=("2026-01-01", "2027-01-01"))
    group = result.primary_group
    assert group.population("numerator").in_population is False
    assert group.denominator_count == 1
    assert group.numerator_count == 0
    assert group.measure_score == 0.0


def test_boolean_measure_denominator_exclusion(tmp_path: Path):
    package = _boolean_package(tmp_path)
    bundle = {
        "resourceType": "Bundle",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "pC", "birthDate": "1980-01-01"}},
            {"resource": _encounter("e1", "office", "finished")},
            {"resource": _observation("o1", "8480-6", 120)},
            {
                "resource": {
                    "resourceType": "Condition",
                    "id": "c1",
                    "code": {"coding": [{"code": "excl-code"}]},
                }
            },
        ],
    }
    result = package.evaluate(bundle, period=("2026-01-01", "2027-01-01"))
    group = result.primary_group
    assert group.population("denominator-exclusion").in_population is True
    assert group.denominator_count == 0
    assert group.measure_score is None


def test_boolean_measure_not_in_initial_population(tmp_path: Path):
    package = _boolean_package(tmp_path)
    bundle = {
        "resourceType": "Bundle",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "pD", "birthDate": "2016-01-01"}},
            {"resource": _encounter("e1", "office", "finished")},
            {"resource": _observation("o1", "8480-6", 120)},
        ],
    }
    result = package.evaluate(bundle, period=("2026-01-01", "2027-01-01"))
    group = result.primary_group
    assert group.population("initial-population").in_population is False
    assert group.denominator_count == 0


# --- integration: measure package (episode-of-care basis) -----------------


def _episode_measure_library() -> dict[str, Any]:
    finished_delivery = {
        "type": "Query",
        "source": [{"alias": "E", "expression": retrieve("Encounter", "Delivery", "type")}],
        "where": {"type": "Equal", "operand": [prop("E", "status"), string("finished")]},
    }
    return make_library(
        "EpisodeLib",
        [
            define("Initial Population", retrieve("Encounter", "Delivery", "type")),
            define("Denominator", expr_ref("Initial Population")),
            define("Numerator", finished_delivery),
        ],
        value_sets=[{"name": "Delivery", "id": "urn:oid:delivery"}],
        parameters=[{"name": "Measurement Period"}],
    )


def _episode_measure_resource() -> dict[str, Any]:
    def population(code: str, expression: str) -> dict[str, Any]:
        return {"code": {"coding": [{"code": code}]}, "criteria": {"expression": expression}}

    return {
        "resourceType": "Measure",
        "url": "http://example.org/Measure/DemoEpisode",
        "name": "DemoEpisode",
        "version": "1.0.0",
        "library": ["http://example.org/Library/EpisodeLib"],
        "scoring": {"coding": [{"code": "proportion"}]},
        "improvementNotation": {"coding": [{"code": "decrease"}]},
        "group": [
            {
                "id": "Group_1",
                "extension": [
                    {
                        "url": "http://hl7.org/fhir/us/cqfmeasures/StructureDefinition/cqfm-populationBasis",
                        "valueCode": "Encounter",
                    }
                ],
                "population": [
                    population("initial-population", "Initial Population"),
                    population("denominator", "Denominator"),
                    population("numerator", "Numerator"),
                ],
            }
        ],
    }


def test_episode_measure_proportion(tmp_path: Path):
    root = _write_package(
        tmp_path / "episode_pkg",
        _episode_measure_resource(),
        [_episode_measure_library()],
        [_value_set_resource("urn:oid:delivery", ["delivery"])],
    )
    package = MeasurePackage.load(root)
    bundle = {
        "resourceType": "Bundle",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "pE", "birthDate": "1990-01-01"}},
            {"resource": _encounter("enc1", "delivery", "finished")},
            {"resource": _encounter("enc2", "delivery", "planned")},
        ],
    }
    result = package.evaluate(bundle, period=("2026-01-01", "2027-01-01"))
    group = result.primary_group
    assert group is not None
    assert group.basis == "Encounter"
    assert group.population("initial-population").count == 2
    assert group.population("denominator").count == 2
    assert group.population("numerator").count == 1
    assert group.numerator_count == 1
    assert group.denominator_count == 2
    assert group.measure_score == 0.5
