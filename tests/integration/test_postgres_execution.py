from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from cql_sdk.api import load_library_from_cql_text
from cql_sdk.postgres import PostgresExecutor, PostgresFHIRStore
from tests.fixtures.cql import SAMPLE_MEASURE

_DATABASE_URL = os.getenv("POSTGRES_TEST_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _DATABASE_URL, reason="POSTGRES_TEST_URL is not configured"),
]


def test_postgres_executes_fhir_retrieve_definition():
    assert _DATABASE_URL is not None
    patient_id = "postgres-integration-patient"
    store = PostgresFHIRStore(database_url=_DATABASE_URL)
    store.initialize()
    store.upsert_bundle(
        {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": patient_id,
                        "birthDate": "1980-01-01",
                    }
                },
                {
                    "resource": {
                        "resourceType": "Encounter",
                        "id": "postgres-integration-encounter",
                        "subject": {"reference": f"Patient/{patient_id}"},
                        "status": "finished",
                        "period": {
                            "start": "2025-04-01T00:00:00Z",
                            "end": "2025-04-02T00:00:00Z",
                        },
                        "type": [
                            {
                                "coding": [
                                    {
                                        "system": "http://snomed.info/sct",
                                        "code": "44054006",
                                    }
                                ]
                            }
                        ],
                    }
                },
            ],
        }
    )
    store.upsert_value_set(
        {
            "resourceType": "ValueSet",
            "url": "urn:oid:diabetes",
            "expansion": {
                "contains": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": "44054006",
                    }
                ]
            },
        }
    )

    library = load_library_from_cql_text(SAMPLE_MEASURE)
    result = PostgresExecutor(database_url=_DATABASE_URL).execute(
        library,
        definition="Initial Population",
        patient_id=patient_id,
        parameters={
            "Measurement Period": (
                datetime(2025, 1, 1, tzinfo=UTC),
                datetime(2026, 1, 1, tzinfo=UTC),
            )
        },
    )

    assert result is True
