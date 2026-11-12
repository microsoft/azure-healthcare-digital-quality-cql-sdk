"""Execute compiled CQL definitions on PostgreSQL."""

from __future__ import annotations

from typing import Any, Protocol

from cql_sdk.elm.models.library import Library
from cql_sdk.postgres.compiler import PostgresCompiler
from cql_sdk.postgres.driver import connect


class _Cursor(Protocol):
    def execute(self, query: str, params: tuple[Any, ...]) -> Any: ...

    def fetchone(self) -> Any: ...

    def close(self) -> None: ...


class _Connection(Protocol):
    def cursor(self) -> _Cursor: ...

    def close(self) -> None: ...


class PostgresExecutor:
    """Compile and execute CQL definitions through a PostgreSQL connection."""

    def __init__(
        self,
        *,
        connection: _Connection | None = None,
        database_url: str | None = None,
        schema: str = "public",
    ) -> None:
        if connection is None and database_url is None:
            raise ValueError("Provide either a PostgreSQL connection or database_url.")
        self.connection = connection
        self.database_url = database_url
        self.schema = schema

    def execute(
        self,
        library: Library,
        *,
        definition: str,
        parameters: dict[str, Any] | None = None,
        patient_id: str | None = None,
    ) -> Any:
        """Compile and execute one definition, returning its result value."""
        query = PostgresCompiler(
            library,
            parameters=parameters,
            patient_id=patient_id,
            schema=self.schema,
        ).compile(definition)
        connection, owned = self._get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute(query.sql, query.parameters)
            row = cursor.fetchone()
            if row is None:
                return None
            if isinstance(row, dict):
                return row.get("result")
            return row[0]
        finally:
            cursor.close()
            if owned:
                connection.close()

    def _get_connection(self) -> tuple[_Connection, bool]:
        if self.connection is not None:
            return self.connection, False
        return connect(self.database_url), True
