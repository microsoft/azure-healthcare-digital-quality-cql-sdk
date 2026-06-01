import pytest

pyspark = pytest.importorskip("pyspark")

from pyspark.sql import SparkSession  # noqa: E402

from cql_sdk.spark import SparkInvocation  # noqa: E402


@pytest.mark.spark
def test_spark_invocation_returns_dataframe(hello_world_elm_path):
    spark = (
        SparkSession.builder.master("local[1]").appName("cql-sdk-tests").getOrCreate()
    )
    try:
        inv = SparkInvocation.from_elm_path(hello_world_elm_path, spark=spark)
        df = inv.run(definition="Sum")
        assert df.count() == 1
    finally:
        spark.stop()
