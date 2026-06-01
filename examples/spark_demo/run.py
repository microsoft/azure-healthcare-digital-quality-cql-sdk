"""Run a library against a Spark DataFrame (requires `--extra spark`)."""

from __future__ import annotations

from pathlib import Path

from pyspark.sql import SparkSession

from cql_sdk.spark import SparkInvocation

ELM = Path(__file__).resolve().parents[1] / "hello_world" / "HelloWorld.elm.json"


def main() -> None:
    spark = SparkSession.builder.master("local[1]").appName("cql-sdk-demo").getOrCreate()
    try:
        inv = SparkInvocation.from_elm_path(ELM, spark=spark)
        df = inv.run(definition="Greeting")
        df.show(truncate=False)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
