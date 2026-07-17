"""Load and evaluate a self-contained DQM (FHIR eCQM) measure package.

A *measure package* is a directory containing everything needed to evaluate a
FHIR electronic clinical quality measure without a network connection:

    <package>/
        measure.json              # the FHIR Measure resource
        libraries/*.json          # ELM libraries (primary + dependencies)
        valuesets/*.json          # expanded FHIR ValueSet resources (or a Bundle)

This mirrors the artifacts published in the official MADiE / eCQI measure
packages (the ELM is the pre-translated output of the reference CQL-to-ELM
translator, so the SDK does not need to compile QI-Core CQL itself).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from cql_sdk.dqm.measure import Measure
from cql_sdk.dqm.model_info import resolve_data_type
from cql_sdk.dqm.results import MeasureResult
from cql_sdk.dqm.scoring import evaluate_measure
from cql_sdk.elm.serialization.loader import load_library_from_string
from cql_sdk.fhir.retrieve import BundleDataSource
from cql_sdk.fhir.terminology import StaticTerminologyProvider
from cql_sdk.invocation.toolkit import InvocationToolkit
from cql_sdk.runtime.context import RuntimeContext
from cql_sdk.runtime.intervals import Interval


class QICoreDataSource:
    """FHIR bundle data source that resolves QI-Core profile retrieves.

    Delegates to :class:`BundleDataSource` after mapping the profile-typed
    ``data_type`` (e.g. ``USCoreBloodPressureProfile``) to its base FHIR
    resource type (``Observation``).
    """

    def __init__(self, bundle: dict[str, Any]) -> None:
        self._inner = BundleDataSource(bundle)
        self.subject = self._inner.subject

    def retrieve(
        self,
        *,
        data_type: str,
        code_property: str | None = None,
        codes: Any | None = None,
        date_property: str | None = None,
        date_range: Any | None = None,
        context: Any | None = None,
    ) -> Any:
        return self._inner.retrieve(
            data_type=resolve_data_type(data_type),
            code_property=code_property,
            codes=codes,
            date_property=date_property,
            date_range=date_range,
            context=context,
        )


@dataclass(slots=True)
class MeasurePackage:
    """A loaded DQM measure package ready for evaluation."""

    measure: Measure
    toolkit: InvocationToolkit
    primary_library: str
    terminology: StaticTerminologyProvider | None = None

    @classmethod
    def load(cls, directory: str | Path) -> MeasurePackage:
        root = Path(directory)
        if not root.exists():
            raise FileNotFoundError(f"Measure package directory not found: {root}")

        measure = _find_measure(root)

        toolkit = InvocationToolkit()
        registered_ids: list[str] = []
        for lib_file in _library_files(root):
            library = load_library_from_string(lib_file.read_text(encoding="utf-8"))
            toolkit.register(library)
            registered_ids.append(library.identifier.id)

        primary = measure.primary_library_name or (registered_ids[0] if registered_ids else None)
        if primary is None or not toolkit.has(primary):
            raise ValueError(
                f"Primary library '{primary}' referenced by the Measure is not present "
                f"in the package (registered: {registered_ids})."
            )

        terminology = _load_terminology(root)
        return cls(
            measure=measure,
            toolkit=toolkit,
            primary_library=primary,
            terminology=terminology,
        )

    def evaluate(
        self,
        bundle: dict[str, Any],
        *,
        period: Interval | tuple[Any, Any] | None = None,
    ) -> MeasureResult:
        """Evaluate the measure against a single subject's FHIR ``bundle``."""
        # Results are memoised per (library, definition, params) inside the
        # toolkit; clear before each subject so patients never share state.
        self.toolkit.clear_cache()

        data_source = QICoreDataSource(bundle)
        context = RuntimeContext.default()
        context.data_source = data_source
        context.subject = data_source.subject
        context.terminology = self.terminology

        parameters: dict[str, Any] | None = None
        if period is not None:
            parameters = {"Measurement Period": _as_interval(period)}

        return evaluate_measure(
            self.measure,
            self.toolkit,
            self.primary_library,
            context,
            parameters=parameters,
        )


# --- loading helpers ------------------------------------------------------


def _find_measure(root: Path) -> Measure:
    candidates = [root / "measure.json", *sorted(root.glob("*.json"))]
    seen: set[Path] = set()
    for path in candidates:
        if path in seen or not path.exists():
            continue
        seen.add(path)
        try:
            import json

            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(payload, dict) and payload.get("resourceType") == "Measure":
            return Measure.from_resource(payload)
    raise ValueError(f"No FHIR Measure resource found in package: {root}")


def _library_files(root: Path) -> list[Path]:
    lib_dir = root / "libraries"
    if lib_dir.exists():
        return sorted(lib_dir.glob("*.json"))
    return sorted(root.glob("*.elm.json"))


def _load_terminology(root: Path) -> StaticTerminologyProvider | None:
    vs_dir = root / "valuesets"
    if vs_dir.exists():
        return StaticTerminologyProvider(vs_dir)
    for name in ("terminology.json", "valuesets.json"):
        bundle_file = root / name
        if bundle_file.exists():
            provider = StaticTerminologyProvider()
            import json

            try:
                provider.ingest(json.loads(bundle_file.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                return provider
            return provider
    return None


def _as_interval(period: Interval | tuple[Any, Any]) -> Interval:
    if isinstance(period, Interval):
        return period
    low, high = period
    return Interval(low=_coerce_dt(low), high=_coerce_dt(high), low_closed=True, high_closed=False)


def _coerce_dt(value: Any) -> Any:
    if isinstance(value, str):
        text = value.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return value
        return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.replace(tzinfo=None)
    return value
