from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from cql_sdk.api import load_library_from_cql_text
from cql_sdk.postgres import PostgresCompiler, PostgresExecutor, PostgresFHIRStore
from cql_sdk.postgres.driver import connect
from tests.fixtures.cql import SAMPLE_MEASURE, TINY_LIBRARY


@pytest.mark.unit
def test_compiler_parameterizes_scalar_definition():
    library = load_library_from_cql_text(TINY_LIBRARY)

    query = PostgresCompiler(library).compile("One Plus Two")

    assert query.sql == "SELECT (%s + %s) AS result"
    assert query.parameters == (1, 2)


@pytest.mark.unit
def test_compiler_translates_fhir_retrieve_query_to_jsonb_sql():
    library = load_library_from_cql_text(SAMPLE_MEASURE)
    period = (
        datetime(2025, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 1, tzinfo=UTC),
    )

    query = PostgresCompiler(
        library,
        parameters={"Measurement Period": period},
        patient_id="patient-1",
    ).compile("Initial Population")

    assert "fhir_resources" in query.sql
    assert "terminology_codes" in query.sql
    assert "EXISTS" in query.sql
    assert "jsonb_extract_path" in query.sql
    assert "Encounter" in query.parameters
    assert "urn:oid:diabetes" in query.parameters
    assert query.parameters.count("patient-1") >= 2


@pytest.mark.unit
def test_compiler_resolves_implicit_sort_property_on_query_alias():
        library = load_library_from_cql_text(
                """\
library Sorted version '1'
using FHIR version '4.0.1'
context Patient

define "Most Recent":
    Last([Observation] O sort by effective as dateTime)
"""
        )

        query = PostgresCompiler(library, patient_id="patient-1").compile("Most Recent")

        assert "__cql_sort_0" in query.sql
        assert "ORDER BY selected_rows.__cql_sort_0 DESC" in query.sql
        assert "effective" in query.parameters


class _FakeCursor:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.executed: tuple[str, tuple[Any, ...]] | None = None
        self.closed = False

    def execute(self, sql: str, parameters: tuple[Any, ...]) -> None:
        self.executed = (sql, parameters)

    def fetchone(self) -> tuple[Any]:
        return (self.result,)

    def close(self) -> None:
        self.closed = True


class _FakeConnection:
    def __init__(self, result: Any) -> None:
        self.cursor_instance = _FakeCursor(result)

    def cursor(self) -> _FakeCursor:
        return self.cursor_instance


@pytest.mark.unit
def test_executor_runs_compiled_query_on_supplied_connection():
    library = load_library_from_cql_text(TINY_LIBRARY)
    connection = _FakeConnection(3)
    executor = PostgresExecutor(connection=connection)

    result = executor.execute(library, definition="One Plus Two")

    assert result == 3
    assert connection.cursor_instance.executed == (
        "SELECT (%s + %s) AS result",
        (1, 2),
    )
    assert connection.cursor_instance.closed is True


class _FakeWriteCursor:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self.closed = False

    def execute(self, sql: str, parameters: tuple[Any, ...] = ()) -> None:
        self.executed.append((sql, parameters))

    def close(self) -> None:
        self.closed = True


class _FakeWriteConnection:
    def __init__(self) -> None:
        self.cursor_instance = _FakeWriteCursor()
        self.commits = 0
        self.rollbacks = 0

    def cursor(self) -> _FakeWriteCursor:
        return self.cursor_instance

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


@pytest.mark.unit
def test_store_upserts_bundle_with_patient_scope():
    connection = _FakeWriteConnection()
    store = PostgresFHIRStore(connection=connection)
    bundle = {
        "resourceType": "Bundle",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "patient-1"}},
            {
                "resource": {
                    "resourceType": "Encounter",
                    "id": "encounter-1",
                    "subject": {"reference": "Patient/patient-1"},
                }
            },
        ],
    }

    count = store.upsert_bundle(bundle)

    assert count == 2
    assert connection.commits == 1
    assert connection.rollbacks == 0
    encounter_parameters = connection.cursor_instance.executed[1][1]
    assert encounter_parameters[:3] == ("Encounter", "encounter-1", "patient-1")
    assert "%s::jsonb" in connection.cursor_instance.executed[1][0]


@pytest.mark.unit
def test_store_replaces_patient_bundle_in_one_transaction():
    connection = _FakeWriteConnection()
    store = PostgresFHIRStore(connection=connection)
    bundle = {
        "resourceType": "Bundle",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "patient-1"}},
            {"resource": {"resourceType": "Observation", "id": "observation-1"}},
        ],
    }

    count = store.replace_patient_bundle("patient-1", bundle)

    assert count == 2
    assert connection.commits == 1
    assert connection.rollbacks == 0
    delete_sql, delete_parameters = connection.cursor_instance.executed[0]
    assert delete_sql.startswith("DELETE FROM")
    assert delete_parameters == ("patient-1", "patient-1")
    assert connection.cursor_instance.executed[2][1][2] == "patient-1"


@pytest.mark.unit
def test_store_flattens_expanded_value_set_codes():
    connection = _FakeWriteConnection()
    store = PostgresFHIRStore(connection=connection)
    value_set = {
        "resourceType": "ValueSet",
        "url": "urn:oid:diabetes",
        "version": "1",
        "expansion": {
            "contains": [
                {
                    "system": "http://snomed.info/sct",
                    "code": "44054006",
                    "display": "Diabetes mellitus type 2",
                }
            ]
        },
    }

    count = store.upsert_value_set(value_set)

    assert count == 1
    assert connection.cursor_instance.executed[0][1] == (
        "urn:oid:diabetes",
        "1",
        "http://snomed.info/sct",
        "44054006",
        "Diabetes mellitus type 2",
    )


@pytest.mark.unit
def test_driver_uses_pgpassword_when_url_has_no_password(monkeypatch):
    captured: dict[str, Any] = {}

    class _FakeDriver:
        @staticmethod
        def connect(**options: Any) -> object:
            captured.update(options)
            return object()

    monkeypatch.setenv("PGPASSWORD", "secret-from-environment")
    monkeypatch.setattr(
        "cql_sdk.postgres.driver.import_module",
        lambda _name: _FakeDriver,
    )

    connect("postgresql://dqadmin@postgres.example.test:5432/dq?sslmode=require")

    assert captured["password"] == "secret-from-environment"
    assert captured["ssl_context"] is True
