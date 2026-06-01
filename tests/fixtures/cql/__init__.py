"""CQL source fixtures used by parser/translator tests.

These constants are inline so test files don't depend on filesystem layout.
"""

from __future__ import annotations

TINY_LIBRARY = """\
library Tiny version '1'
context Patient

define "One Plus Two":
  1 + 2
"""


HEADER_WITH_ALL_DECLS = """\
library Header version '0.1'
using FHIR version '4.0.1'
include FHIRHelpers version '4.0.1' called FHIRHelpers

codesystem "LOINC": 'http://loinc.org'
valueset "Diabetes": 'http://example.org/vs/diabetes'
code "HbA1c": '4548-4' from "LOINC" display 'Hemoglobin A1c'

parameter "Measurement Period" Interval<DateTime>
  default Interval[@2025-01-01T00:00:00.0, @2026-01-01T00:00:00.0)

context Patient

define "Empty":
  null
"""


SAMPLE_MEASURE = """\
library SampleMeasure version '1'

using FHIR version '4.0.1'
include FHIRHelpers version '4.0.1' called FHIRHelpers

codesystem "LOINC": 'http://loinc.org'
valueset "Diabetes": 'urn:oid:diabetes'
code "HbA1c": '4548-4' from "LOINC" display 'A1c'

parameter "Measurement Period" Interval<DateTime>
  default Interval[@2025-01-01T00:00:00.0, @2026-01-01T00:00:00.0)

context Patient

define "Initial Population":
  AgeInYearsAt(date from start of "Measurement Period") >= 18
    and AgeInYearsAt(date from start of "Measurement Period") < 75
    and exists "Diabetes Encounters"

define "Diabetes Encounters":
  [Encounter: "Diabetes"] E
    where E.status = 'finished'
      and E.period during "Measurement Period"

define "Denominator":
  "Initial Population"

define "Numerator":
  exists (
    [Observation: "Diabetes"] O
      where O.value as Quantity > 9.0 '%'
        and O.effective as dateTime during "Measurement Period"
  )

define "SDE Ethnicity":
  Patient.ethnicity
"""
