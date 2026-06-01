"""Quick smoke test that runs the CQL→ELM pipeline on a tiny snippet."""

from __future__ import annotations

import json
import sys

from cql_sdk.compiler.cql_to_elm import translate

SRC = """\
library Smoke version '1'
using FHIR version '4.0.1'
context Patient

parameter "Measurement Period" Interval<DateTime>
  default Interval[@2025-01-01T00:00:00.0, @2026-01-01T00:00:00.0)

codesystem "LOINC": 'http://loinc.org'
valueset "Diabetes": 'urn:vs:diabetes'
code "HbA1c": '4548-4' from "LOINC" display 'Hemoglobin A1c'

define "Adult":
  AgeInYearsAt(start of "Measurement Period") >= 18 and
  AgeInYearsAt(start of "Measurement Period") < 75

define "Has Encounter":
  exists ([Encounter: "Diabetes"] E
    where E.period during "Measurement Period")

define "Initial Population":
  "Adult" and "Has Encounter"
"""


def main() -> int:
    elm = translate(SRC)
    json.dump(elm, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
