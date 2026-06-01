"""Spark-facing facade that mirrors the invocation toolkit shape."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from cql_sdk.elm.serialization.loader import load_library_from_path
from cql_sdk.invocation.toolkit import InvocationToolkit

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession


class SparkInvocation:
    """Run a library against Spark-backed input data.

    This adapter is intentionally minimal: it loads an ELM library with the
    core Python path (zero Spark involvement) and exposes a ``run`` method
    that yields a :class:`pyspark.sql.DataFrame`. The Spark dependency is
    isolated behind the deferred import so the rest of ``cql_sdk`` never
    pulls ``pyspark``.
    """

    def __init__(
        self,
        *,
        spark: SparkSession,
        toolkit: InvocationToolkit,
        default_library_identifier: str | None = None,
    ) -> None:
        self._spark = spark
        self._toolkit = toolkit
        self._default_library_identifier = default_library_identifier

    @classmethod
    def from_elm_path(cls, path: str | Path, *, spark: SparkSession) -> SparkInvocation:
        toolkit = InvocationToolkit()
        library = load_library_from_path(Path(path))
        toolkit.register(library)
        return cls(
            spark=spark,
            toolkit=toolkit,
            default_library_identifier=str(library.identifier),
        )

    def run(
        self,
        *,
        definition: str,
        library_identifier: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> DataFrame:
        ident = library_identifier or self._default_library_identifier
        if ident is None:
            library = next(iter(self._toolkit._registry))
            ident = str(library.identifier)
        result = self._toolkit.invoke(
            library_identifier=ident,
            definition=definition,
            parameters=parameters,
        )
        rows = result if isinstance(result, list) else [{"value": result}]
        normalized = [r if isinstance(r, dict) else {"value": r} for r in rows]
        return self._spark.createDataFrame(normalized)
