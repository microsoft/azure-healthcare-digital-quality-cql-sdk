"""QI-Core / US-Core model information.

The 2026 FHIR eCQMs are authored against the QI-Core 6.0.0 model, whose
retrieves are typed by *profile* (e.g. ``ConditionProblemsHealthConcerns`` or
``USCoreBloodPressureProfile``) rather than by the base FHIR resource type.

This module provides the minimal model information the runtime needs: a map
from QI-Core / US-Core profile names to their underlying FHIR R4 resource type,
so profile-typed retrieves resolve against a plain FHIR bundle.
"""

from __future__ import annotations

# Profile (or model type) name -> base FHIR R4 resourceType.
#
# Keys are the *local* type names as they appear in QI-Core ELM retrieve
# ``dataType`` discriminators (namespace already stripped by the retrieve
# operator). Base resource types map to themselves.
PROFILE_TO_RESOURCE: dict[str, str] = {
    # Condition profiles
    "Condition": "Condition",
    "ConditionProblemsHealthConcerns": "Condition",
    "ConditionEncounterDiagnosis": "Condition",
    # Observation profiles
    "Observation": "Observation",
    "LaboratoryResultObservation": "Observation",
    "ObservationScreeningAssessment": "Observation",
    "SimpleObservation": "Observation",
    "USCoreBloodPressureProfile": "Observation",
    "USCoreHeartRateProfile": "Observation",
    "USCoreBMIProfile": "Observation",
    "USCorePulseOximetryProfile": "Observation",
    "VitalSignsProfile": "Observation",
    # Encounter / procedures / requests
    "Encounter": "Encounter",
    "Procedure": "Procedure",
    "MedicationRequest": "MedicationRequest",
    "MedicationAdministration": "MedicationAdministration",
    "MedicationDispense": "MedicationDispense",
    "DeviceRequest": "DeviceRequest",
    "ServiceRequest": "ServiceRequest",
    "Immunization": "Immunization",
    # Financial / coverage / other
    "Coverage": "Coverage",
    "Claim": "Claim",
    "Patient": "Patient",
    "Medication": "Medication",
    "Location": "Location",
    "Practitioner": "Practitioner",
    "DiagnosticReport": "DiagnosticReport",
    "AllergyIntolerance": "AllergyIntolerance",
    "FamilyMemberHistory": "FamilyMemberHistory",
    "Device": "Device",
}


def resolve_data_type(data_type: str) -> str:
    """Return the base FHIR resourceType for a QI-Core retrieve ``dataType``.

    Unknown types are returned unchanged so callers still work against plain
    FHIR bundles.
    """
    return PROFILE_TO_RESOURCE.get(data_type, data_type)
