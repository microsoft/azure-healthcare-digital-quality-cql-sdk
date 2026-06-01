"""End-to-end tests: parse each project measure file and load it as ELM."""

from __future__ import annotations

from pathlib import Path

import pytest

from cql_sdk.api import load_library_from_cql
from cql_sdk.compiler.cql_to_elm import compile_file

MEASURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "cql" / "measures"


@pytest.fixture(scope="module")
def measure_files() -> list[Path]:
    files = sorted(MEASURES_DIR.glob("*.cql"))
    assert files, f"No .cql fixtures under {MEASURES_DIR}"
    return files


@pytest.mark.integration
def test_each_measure_translates_to_elm(measure_files):
    for path in measure_files:
        elm = compile_file(path)
        lib = elm["library"]
        assert lib["identifier"]["id"], f"no library identifier for {path.name}"
        assert lib["statements"]["def"], f"no statements for {path.name}"


@pytest.mark.integration
def test_each_measure_loads_through_sdk_loader(measure_files):
    for path in measure_files:
        lib = load_library_from_cql(path)
        assert lib.identifier.id
        assert lib.definitions, f"no definitions parsed from {path.name}"


@pytest.mark.integration
def test_cms122_has_expected_definitions():
    lib = load_library_from_cql(MEASURES_DIR / "CMS122v11_DiabetesHbA1cPoorControl.cql")
    assert lib.identifier.id == "CMS122"
    expected = {
        "Initial Population",
        "Qualifying Encounters",
        "Diabetes Diagnosis",
        "Denominator",
        "Numerator",
        "Has Most Recent HbA1c Greater Than 9",
        "Most Recent HbA1c",
    }
    assert expected.issubset(set(lib.definitions))
    assert "Measurement Period" in lib.parameters
    assert "Diabetes" in lib.value_sets


@pytest.mark.integration
def test_cms165_has_expected_definitions():
    lib = load_library_from_cql(MEASURES_DIR / "CMS165v9_ControllingHighBloodPressure.cql")
    assert lib.identifier.id == "CMS165"
    assert "Initial Population" in lib.definitions
    assert "Numerator" in lib.definitions


@pytest.mark.integration
def test_epc02_has_expected_definitions():
    lib = load_library_from_cql(MEASURES_DIR / "ePC02_SevereObstetricComplications.cql")
    assert lib.identifier.id == "ePC02"
    assert "Has Mechanical Ventilation" in lib.definitions
