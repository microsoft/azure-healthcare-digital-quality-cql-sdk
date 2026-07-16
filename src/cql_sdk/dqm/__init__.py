"""Digital Quality Measure (DQM) evaluation for FHIR / QI-Core eCQMs.

This subpackage adds first-class support for the 2026-style FHIR electronic
clinical quality measures (eCQMs): QI-Core-profiled retrieves, multi-library
packages, a FHIR ``Measure`` resource model, and proportion scoring for both
patient-based and episode-of-care measures.

Typical usage::

    from cql_sdk.dqm import MeasurePackage

    package = MeasurePackage.load("packages/CMS165FHIR")
    result = package.evaluate(patient_bundle, period=("2026-01-01", "2027-01-01"))
    print(result.primary_group.measure_score)
"""

from __future__ import annotations

from cql_sdk.dqm.measure import (
    Measure,
    MeasureGroup,
    MeasurePopulation,
    SupplementalDataElement,
)
from cql_sdk.dqm.model_info import PROFILE_TO_RESOURCE, resolve_data_type
from cql_sdk.dqm.package import MeasurePackage, QICoreDataSource
from cql_sdk.dqm.results import GroupResult, MeasureResult, PopulationResult
from cql_sdk.dqm.scoring import evaluate_measure

__all__ = [
    "PROFILE_TO_RESOURCE",
    "GroupResult",
    "Measure",
    "MeasureGroup",
    "MeasurePackage",
    "MeasurePopulation",
    "MeasureResult",
    "PopulationResult",
    "QICoreDataSource",
    "SupplementalDataElement",
    "evaluate_measure",
    "resolve_data_type",
]
