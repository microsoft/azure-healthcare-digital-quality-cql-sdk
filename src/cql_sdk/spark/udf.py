"""UDF factories that wrap CQL definitions for use in Spark jobs."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from cql_sdk.invocation.toolkit import InvocationToolkit

if TYPE_CHECKING:
    from cql_sdk.elm.models.library import Library


def make_definition_udf(
    toolkit: InvocationToolkit,
    *,
    library: Library,
    definition: str,
) -> Callable[..., Any]:
    """Return a plain Python callable usable with ``pyspark.sql.functions.udf``."""
    toolkit.register(library)

    def _udf(*args: Any) -> Any:
        # Positional args map to ELM parameters by index via a conventional
        # ``arg0, arg1, ...`` naming. Callers needing named parameters should
        # wrap this UDF themselves.
        params = {f"arg{i}": v for i, v in enumerate(args)}
        return toolkit.invoke(
            library_identifier=library.identifier,
            definition=definition,
            parameters=params,
        )

    _udf.__name__ = f"cql_{definition}"
    return _udf
