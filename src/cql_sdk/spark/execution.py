"""High-level helpers for running a library across Spark datasets."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cql_sdk.invocation.toolkit import InvocationToolkit

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

    from cql_sdk.elm.models.library import Library


def evaluate_over_dataframe(
    *,
    df: DataFrame,
    library: Library,
    definition: str,
    toolkit: InvocationToolkit | None = None,
) -> list[Any]:
    """Evaluate ``definition`` once per row of ``df`` (collected locally).

    Intended for small / offline datasets; production Spark usage should
    prefer registered UDFs (see :mod:`cql_sdk.spark.udf`).
    """
    tk = toolkit or InvocationToolkit()
    tk.register(library)
    return [
        tk.invoke(
            library_identifier=library.identifier,
            definition=definition,
            parameters=row.asDict(recursive=True),
        )
        for row in df.collect()
    ]
