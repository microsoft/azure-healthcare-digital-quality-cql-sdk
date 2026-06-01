"""Abstractions: protocols and ABCs describing stable SDK seams.

Concrete implementations live under :mod:`cql_sdk.runtime`,
:mod:`cql_sdk.fhir`, :mod:`cql_sdk.spark`, and :mod:`cql_sdk.packaging`.
"""

from cql_sdk.abstractions.data_source import DataSource
from cql_sdk.abstractions.invocation import Invoker
from cql_sdk.abstractions.operators import OperatorRegistry
from cql_sdk.abstractions.packaging import PackageWriter
from cql_sdk.abstractions.terminology import TerminologyProvider
from cql_sdk.abstractions.type_conversion import TypeConverter

__all__ = [
    "DataSource",
    "Invoker",
    "OperatorRegistry",
    "PackageWriter",
    "TerminologyProvider",
    "TypeConverter",
]
