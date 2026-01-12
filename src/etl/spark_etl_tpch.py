#!/usr/bin/env python3
"""Spark ETL for TPC-H Benchmark - Kubernetes/Spark Operator compatible version.

This implementation executes TPC-H Query 3 (Shipping Priority) using PySpark on EKS.
It reads TPC-H tables from S3, performs complex joins and aggregations, and tracks
detailed performance metrics.
"""
# ruff: noqa: S108
# S108: /tmp/output is the standard path in Kubernetes pods, not a security issue

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, desc
from pyspark.sql.functions import sum as spark_sum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_spark_session() -> SparkSession:
    """Get or create Spark session - works with Spark Operator.

    Returns:
        SparkSession: Configured Spark session
    """
    return SparkSession.builder.appName("SparkTPCHETL").getOrCreate()


class SparkETLTPCH:
    """PySpark implementation of TPC-H Query 3 (Shipping Priority).

    This class implements the TPC-H Query 3 benchmark query, which involves:
    - Multi-table joins (customer, orders, lineitem)
    - Complex filtering predicates
    - Revenue aggregation
    - Sorting and limiting results
    """

    def __init__(
        self,
        spark: SparkSession,
        s3_input_path: str,
        s3_output_path: str,
        scale_factor: int = 10,
    ):
        """Initialize Spark ETL job.

        Args:
            spark: SparkSession instance
            s3_input_path: S3 path to TPC-H data (e.g., s3://bucket/tpch-sf10/)
            s3_output_path: S3 path for results (e.g., s3://bucket/results/)
            scale_factor: TPC-H scale factor (10 or 100)
        """
        self.spark = spark
        # Convert s3:// to s3a:// for Hadoop compatibility
        self.s3_input_path = s3_input_path.replace("s3://", "s3a://").rstrip("/")
        self.s3_output_path = s3_output_path.replace("s3://", "s3a://").rstrip("/")
        self.scale_factor = scale_factor
        self.metrics = {
            "startup_time": 0.0,
            "execution_time": 0.0,
            "peak_memory_mb": 0,
            "bytes_read": 0,
            "bytes_written": 0,
        }

    def load_tables(self) -> dict[str, DataFrame]:
        """Load required TPC-H tables from S3.

        Loads customer, orders, and lineitem tables needed for Query 3.
        Validates that schemas match TPC-H specification.

        Returns:
            Dict[str, DataFrame]: Dictionary mapping table names to DataFrames
        """
        logger.info("Loading TPC-H tables from %s", self.s3_input_path)

        tables = {}

        # Load customer table - single parquet file
        customer_path = f"{self.s3_input_path}/customer.parquet"
        logger.info("Loading customer table from %s", customer_path)
        tables["customer"] = self.spark.read.parquet(customer_path)
        logger.info("Customer table: %d rows", tables["customer"].count())

        # Load orders table - single parquet file
        orders_path = f"{self.s3_input_path}/orders.parquet"
        logger.info("Loading orders table from %s", orders_path)
        tables["orders"] = self.spark.read.parquet(orders_path)
        logger.info("Orders table: %d rows", tables["orders"].count())

        # Load lineitem table - single parquet file
        lineitem_path = f"{self.s3_input_path}/lineitem.parquet"
        logger.info("Loading lineitem table from %s", lineitem_path)
        tables["lineitem"] = self.spark.read.parquet(lineitem_path)
        logger.info("Lineitem table: %d rows", tables["lineitem"].count())

        # Validate schemas
        self._validate_schemas(tables)

        return tables

    def _validate_schemas(self, tables: dict[str, DataFrame]) -> None:
        """Validate that table schemas match TPC-H specification.

        Args:
            tables: Dictionary of loaded DataFrames

        Raises:
            ValueError: If required columns are missing
        """
        # Required columns for Query 3
        required_columns = {
            "customer": ["c_custkey", "c_mktsegment"],
            "orders": ["o_orderkey", "o_custkey", "o_orderdate", "o_shippriority"],
            "lineitem": ["l_orderkey", "l_shipdate", "l_extendedprice", "l_discount"],
        }

        for table_name, required_cols in required_columns.items():
            df = tables[table_name]
            actual_cols = set(df.columns)
            missing_cols = set(required_cols) - actual_cols

            if missing_cols:
                raise ValueError(
                    f"Table {table_name} missing required columns: {missing_cols}"
                )

        logger.info("Schema validation passed for all tables")

    def execute_query(self, tables: dict[str, DataFrame]) -> DataFrame:
        """Execute TPC-H Query 3 (Shipping Priority).

        Query logic:
        - Filter customers by market segment (BUILDING)
        - Filter orders by date (< 1995-03-15)
        - Filter lineitem by ship date (> 1995-03-15)
        - Join customer, orders, and lineitem
        - Calculate revenue: sum(l_extendedprice * (1 - l_discount))
        - Group by l_orderkey, o_orderdate, o_shippriority
        - Order by revenue descending, o_orderdate
        - Limit to top 10

        Args:
            tables: Dictionary of loaded DataFrames

        Returns:
            DataFrame: Query results with top 10 shipping priorities
        """
        logger.info("Executing TPC-H Query 3 (Shipping Priority)")

        customer = tables["customer"]
        orders = tables["orders"]
        lineitem = tables["lineitem"]

        # Apply filters
        customer_filtered = customer.filter(col("c_mktsegment") == "BUILDING")
        orders_filtered = orders.filter(col("o_orderdate") < "1995-03-15")
        lineitem_filtered = lineitem.filter(col("l_shipdate") > "1995-03-15")

        # Join tables
        # customer -> orders
        co_join = customer_filtered.join(
            orders_filtered,
            customer_filtered.c_custkey == orders_filtered.o_custkey,
            "inner",
        )

        # (customer + orders) -> lineitem
        result = co_join.join(
            lineitem_filtered,
            co_join.o_orderkey == lineitem_filtered.l_orderkey,
            "inner",
        )

        # Calculate revenue and aggregate
        result = result.withColumn(
            "revenue", col("l_extendedprice") * (1 - col("l_discount"))
        )

        result = result.groupBy("l_orderkey", "o_orderdate", "o_shippriority").agg(
            spark_sum("revenue").alias("revenue")
        )

        # Order and limit
        result = result.orderBy(desc("revenue"), col("o_orderdate")).limit(10)

        logger.info("Query execution complete")
        return result

    def write_results(self, df: DataFrame, timestamp: str) -> None:
        """Write aggregated results to S3.

        Args:
            df: Results DataFrame
            timestamp: Timestamp string for output path
        """
        s3_path = (
            f"{self.s3_output_path}/spark/sf{self.scale_factor}/results_{timestamp}"
        )
        s3a_path = s3_path.replace("s3://", "s3a://")

        logger.info("Writing results to S3: %s", s3_path)
        df.coalesce(1).write.mode("overwrite").parquet(s3a_path)
        logger.info("Results written to S3")


class PerformanceTracker:
    """Tracks performance metrics for Spark jobs.

    Collects startup time, execution time, memory usage, and I/O metrics
    for comprehensive performance analysis.
    """

    def __init__(self):
        """Initialize performance tracker."""
        self.metrics = {
            "framework": "spark",
            "startup_time": 0.0,
            "execution_time": 0.0,
            "peak_memory_mb": 0,
            "bytes_read": 0,
            "bytes_written": 0,
            "timestamp": "",
            "spark_app_id": "",
            "scale_factor": 0,
        }
        self.job_start_time = time.time()

    def record_startup(self, start_time: float, execution_start: float) -> None:
        """Record time from job submission to execution start.

        Args:
            start_time: Job submission timestamp
            execution_start: Execution start timestamp
        """
        self.metrics["startup_time"] = execution_start - start_time
        logger.info("Startup time: %.2fs", self.metrics["startup_time"])

    def record_execution(self, start_time: float, end_time: float) -> None:
        """Record total execution time.

        Args:
            start_time: Execution start timestamp
            end_time: Execution end timestamp
        """
        self.metrics["execution_time"] = end_time - start_time
        logger.info("Execution time: %.2fs", self.metrics["execution_time"])

    def collect_spark_metrics(self, spark: SparkSession) -> None:
        """Collect metrics from Spark context.

        Args:
            spark: SparkSession instance
        """
        sc = spark.sparkContext

        # Get Spark metrics
        self.metrics["spark_app_id"] = sc.applicationId

        # Try to get memory metrics from Spark UI metrics
        try:
            status_tracker = sc.statusTracker()
            executor_infos = status_tracker.getExecutorInfos()

            total_memory = 0
            for executor in executor_infos:
                # Memory is in bytes, convert to MB
                total_memory += executor.totalOnHeapStorageMemory()

            self.metrics["peak_memory_mb"] = total_memory // (1024 * 1024)
        except Exception as e:
            logger.warning("Could not collect memory metrics: %s", e)
            self.metrics["peak_memory_mb"] = 0

        logger.info("Spark App ID: %s", self.metrics["spark_app_id"])
        logger.info("Peak memory: %d MB", self.metrics["peak_memory_mb"])

    def write_metrics(self, s3_path: str, local_path: str, timestamp: str) -> None:
        """Write metrics to S3 and local filesystem as JSON.

        Args:
            s3_path: S3 path for metrics
            local_path: Local path for metrics
            timestamp: Timestamp string for filename
        """
        self.metrics["timestamp"] = timestamp

        # Write to local filesystem
        local_file = f"{local_path}/metrics_{timestamp}.json"
        Path(local_path).mkdir(parents=True, exist_ok=True)

        with open(local_file, "w") as f:
            json.dump(self.metrics, f, indent=2)

        logger.info("Metrics written to %s", local_file)
        logger.info("Metrics: %s", json.dumps(self.metrics, indent=2))


def main():
    """Main entry point for Spark TPC-H ETL."""
    parser = argparse.ArgumentParser(description="Spark ETL for TPC-H Benchmark")
    parser.add_argument(
        "--scale-factor", type=int, default=10, help="TPC-H scale factor (10 or 100)"
    )
    parser.add_argument(
        "--output", type=str, default="/tmp/output", help="Local output path"
    )
    parser.add_argument(
        "--s3-input",
        type=str,
        required=True,
        help="S3 path to TPC-H data (e.g., s3://bucket/tpch-sf10/)",
    )
    parser.add_argument(
        "--s3-output",
        type=str,
        required=True,
        help="S3 path for results (e.g., s3://bucket/results/)",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Spark TPC-H ETL - Kubernetes Mode")
    logger.info("=" * 60)
    logger.info("Scale Factor: %d", args.scale_factor)
    logger.info("S3 Input: %s", args.s3_input)
    logger.info("S3 Output: %s", args.s3_output)
    logger.info("Local Output: %s", args.output)
    logger.info("=" * 60)

    # Initialize performance tracker
    tracker = PerformanceTracker()
    tracker.metrics["scale_factor"] = args.scale_factor

    start_time = time.time()

    # Get Spark session (already configured by Spark Operator)
    spark = get_spark_session()
    logger.info("Spark Master: %s", spark.sparkContext.master)
    logger.info("Spark App ID: %s", spark.sparkContext.applicationId)

    execution_start = time.time()
    tracker.record_startup(start_time, execution_start)

    try:
        # Initialize ETL job
        etl = SparkETLTPCH(
            spark=spark,
            s3_input_path=args.s3_input,
            s3_output_path=args.s3_output,
            scale_factor=args.scale_factor,
        )

        # EXTRACT
        logger.info("EXTRACT: Loading TPC-H tables...")
        extract_start = time.time()
        tables = etl.load_tables()
        logger.info("Tables loaded in %.2fs", time.time() - extract_start)

        # TRANSFORM
        logger.info("TRANSFORM: Executing TPC-H Query 3...")
        transform_start = time.time()
        result_df = etl.execute_query(tables)
        result_count = result_df.count()
        logger.info(
            "Query executed, %d results in %.2fs",
            result_count,
            time.time() - transform_start,
        )

        # LOAD
        logger.info("LOAD: Writing results...")
        load_start = time.time()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        etl.write_results(result_df, timestamp)

        # Also write locally
        local_path = f"{args.output}/results_{timestamp}"
        Path(local_path).mkdir(parents=True, exist_ok=True)
        result_df.coalesce(1).write.mode("overwrite").parquet(local_path)
        logger.info("Results written in %.2fs", time.time() - load_start)

        # Record execution time
        execution_end = time.time()
        tracker.record_execution(execution_start, execution_end)

        # Collect Spark metrics
        tracker.collect_spark_metrics(spark)

        # Write metrics
        tracker.write_metrics(args.s3_output, args.output, timestamp)

        total_time = time.time() - start_time
        logger.info("=" * 60)
        logger.info("COMPLETED in %.2fs", total_time)
        logger.info("Results: %d rows", result_count)
        logger.info("=" * 60)

    except Exception as e:
        logger.error("ETL job failed: %s", e, exc_info=True)
        return 1
    else:
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())
