"""Optional Spark / Microsoft Fabric integration.

This package is only importable when the ``spark`` extra is installed::

    uv sync --extra spark

Core modules under :mod:`cql_sdk` never import ``pyspark``.
"""

from cql_sdk.spark.session import SparkInvocation

__all__ = ["SparkInvocation"]
