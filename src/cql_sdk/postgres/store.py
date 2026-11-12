"""FHIR JSONB and terminology ingestion for PostgreSQL execution."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Protocol

from cql_sdk.postgres.driver import connect

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class _Cursor(Protocol):
    def execute(self, query: str, params: tuple[Any, ...] = ()) -> Any: ...

    def close(self) -> None: ...


class _Connection(Protocol):
    def cursor(self) -> _Cursor: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...


class PostgresFHIRStore:
    """Initialize and populate the PostgreSQL schema consumed by CQL SQL."""

    def __init__(
        self,
        *,
        connection: _Connection | None = None,
        database_url: str | None = None,
        schema: str = "public",
    ) -> None:
        if connection is None and database_url is None:
            raise ValueError("Provide either a PostgreSQL connection or database_url.")
        if not _IDENTIFIER.fullmatch(schema):
            raise ValueError(f"Invalid PostgreSQL schema identifier: {schema!r}")
        self.connection = connection
        self.database_url = database_url
        self.schema = schema

    @property
    def _resources_table(self) -> str:
        return f'"{self.schema}"."fhir_resources"'

    @property
    def _terminology_table(self) -> str:
        return f'"{self.schema}"."terminology_codes"'

    def initialize(self) -> None:
        """Create the schema, FHIR resource table, and terminology table."""
        schema_sql = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")

        def initialize_schema(cursor: _Cursor) -> None:
            cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{self.schema}"')
            cursor.execute(f'SET LOCAL search_path TO "{self.schema}"')
            cursor.execute(schema_sql)

        self._write(initialize_schema)

    def upsert_bundle(self, bundle: dict[str, Any]) -> int:
        """Insert or update every identified FHIR resource in ``bundle``."""
        resources = _bundle_resources(bundle)
        patient_ids = {
            str(resource["id"])
            for resource in resources
            if resource.get("resourceType") == "Patient" and resource.get("id")
        }
        fallback_patient_id = next(iter(patient_ids)) if len(patient_ids) == 1 else None

        rows = _resource_rows(resources, fallback_patient_id=fallback_patient_id)

        def upsert(cursor: _Cursor) -> None:
            self._upsert_resource_rows(cursor, rows)

        self._write(upsert)
        return len(resources)

    def replace_patient_bundle(self, patient_id: str, bundle: dict[str, Any]) -> int:
        """Atomically replace all stored resources for one patient."""
        if not patient_id:
            raise ValueError("patient_id is required to replace a patient bundle.")
        resources = _bundle_resources(bundle)
        rows = _resource_rows(resources, fallback_patient_id=patient_id)
        mismatched = {row[2] for row in rows if row[2] not in {None, patient_id}}
        if mismatched:
            raise ValueError("The FHIR bundle contains resources for another patient.")

        def replace(cursor: _Cursor) -> None:
            cursor.execute(
                f"DELETE FROM {self._resources_table} "
                "WHERE patient_id = %s OR (resource_type = 'Patient' AND resource_id = %s)",
                (patient_id, patient_id),
            )
            self._upsert_resource_rows(cursor, rows)

        self._write(replace)
        return len(resources)

    def upsert_value_set(self, value_set: dict[str, Any]) -> int:
        """Insert or update codes from an expanded FHIR ValueSet resource."""
        value_set_url = value_set.get("url")
        if not isinstance(value_set_url, str) or not value_set_url:
            raise ValueError("An expanded FHIR ValueSet requires a canonical url.")
        version = str(value_set.get("version") or "")
        expansion = value_set.get("expansion")
        contains = expansion.get("contains", []) if isinstance(expansion, dict) else []
        codes = list(_expanded_codes(contains))

        def upsert(cursor: _Cursor) -> None:
            for system, code, display in codes:
                cursor.execute(
                    f"INSERT INTO {self._terminology_table} "
                    "(value_set_url, value_set_version, system, code, display) "
                    "VALUES (%s, %s, %s, %s, %s) "
                    "ON CONFLICT (value_set_url, value_set_version, system, code) "
                    "DO UPDATE SET display = EXCLUDED.display",
                    (value_set_url, version, system, code, display),
                )

        self._write(upsert)
        return len(codes)

    def load_value_sets(self, directory: str | Path | None = None) -> int:
        """Load every expanded FHIR ValueSet from a directory or SDK data."""
        value_sets_dir = Path(directory) if directory is not None else _bundled_value_sets_dir()
        if not value_sets_dir.is_dir():
            raise FileNotFoundError(f"FHIR ValueSet directory not found: {value_sets_dir}")
        count = 0
        for path in sorted(value_sets_dir.glob("*.json")):
            value_set = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value_set, dict) and value_set.get("resourceType") == "ValueSet":
                count += self.upsert_value_set(value_set)
        return count

    def _write(self, operation: Any) -> None:
        connection, owned = self._get_connection()
        cursor = connection.cursor()
        try:
            operation(cursor)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            if owned:
                connection.close()

    def _upsert_resource_rows(
        self,
        cursor: _Cursor,
        rows: list[tuple[str, str, str | None, str]],
    ) -> None:
        for row in rows:
            cursor.execute(
                f"INSERT INTO {self._resources_table} "
                "(resource_type, resource_id, patient_id, resource) "
                "VALUES (%s, %s, %s, %s::jsonb) "
                "ON CONFLICT (resource_type, resource_id) DO UPDATE SET "
                "patient_id = EXCLUDED.patient_id, resource = EXCLUDED.resource, "
                "updated_at = CURRENT_TIMESTAMP",
                row,
            )

    def _get_connection(self) -> tuple[_Connection, bool]:
        if self.connection is not None:
            return self.connection, False
        return connect(self.database_url), True


def _bundle_resources(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    if bundle.get("resourceType") != "Bundle":
        return [bundle]
    resources: list[dict[str, Any]] = []
    for entry in bundle.get("entry", []):
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if isinstance(resource, dict):
            resources.append(resource)
    return resources


def _patient_id(resource: dict[str, Any]) -> str | None:
    if resource.get("resourceType") == "Patient" and isinstance(resource.get("id"), str):
        return str(resource["id"])
    for field in ("subject", "patient", "beneficiary", "individual"):
        reference = resource.get(field)
        reference_value = reference.get("reference") if isinstance(reference, dict) else None
        if isinstance(reference_value, str) and reference_value:
            base = reference_value.split("/_history/", 1)[0].rstrip("/")
            if "/Patient/" in f"/{base}/" or base.startswith("Patient/"):
                return base.rsplit("/", 1)[-1]
    return None


def _resource_rows(
    resources: list[dict[str, Any]],
    *,
    fallback_patient_id: str | None,
) -> list[tuple[str, str, str | None, str]]:
    rows: list[tuple[str, str, str | None, str]] = []
    for resource in resources:
        resource_type = resource.get("resourceType")
        resource_id = resource.get("id")
        if not isinstance(resource_type, str) or not isinstance(resource_id, str):
            raise ValueError("Every stored FHIR resource requires resourceType and id.")
        patient_id = _patient_id(resource) or fallback_patient_id
        rows.append((resource_type, resource_id, patient_id, json.dumps(resource)))
    return rows


def _expanded_codes(values: Any) -> list[tuple[str, str, str | None]]:
    if not isinstance(values, list):
        return []
    codes: list[tuple[str, str, str | None]] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        system = value.get("system")
        code = value.get("code")
        if isinstance(system, str) and isinstance(code, str):
            display = value.get("display")
            codes.append((system, code, str(display) if display is not None else None))
        codes.extend(_expanded_codes(value.get("contains")))
    return codes


def _bundled_value_sets_dir() -> Path:
    package_data = Path(__file__).resolve().parents[1] / "data" / "valuesets"
    if package_data.is_dir():
        return package_data
    source_fixtures = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "valuesets"
    return source_fixtures
