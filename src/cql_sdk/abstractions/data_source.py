"""Data source protocol used by retrieve-style ELM nodes."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DataSource(Protocol):
    """Abstract source of clinical/patient data.

    Implementations may be backed by in-memory FHIR bundles, file-based
    fixtures, REST FHIR servers, or Spark DataFrames.
    """

    def retrieve(
        self,
        *,
        data_type: str,
        code_property: str | None = None,
        codes: Iterable[Any] | None = None,
        date_property: str | None = None,
        date_range: Any | None = None,
        context: Any | None = None,
    ) -> Iterable[Any]:
        """Retrieve resources/records matching the given criteria."""
