"""Spark ETL - Incremental Pipeline Implementation

This ETL pipeline is built incrementally with clearly defined steps:
- Step 1: Read CSV
- Step 2: Transform data
- Step 3: Load to storage
- Step 4: Merge operations
- Step 5: Additional features

Each step is timed for performance comparison.
"""

import logging
import time
from pathlib import Path
from typing import Any

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, countDistinct
from pyspark.sql.types import StringType, TimestampType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SparkPipeline:
    """Incremental ETL pipeline using Spark."""

    def __init__(self, input_path: str, output_path: str):
        """Initialize pipeline with input/output paths.

        Args:
            input_path: Path to input CSV file
            output_path: Path to output directory
        """
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.output_path.mkdir(parents=True, exist_ok=True)

        # Initialize Spark
        self.spark = (
            SparkSession.builder.appName("IncrementalSparkETL")
            .master("local[*]")
            .config("spark.sql.adaptive.enabled", "true")
            .getOrCreate()
        )

        self.df = None
        self.metrics = {
            "step_1_read": 0.0,
            "step_2_transform": 0.0,
            "step_3_load": 0.0,
            "step_4_merge": 0.0,
            "step_5_additional": 0.0,
        }

    def step_1_read(self):
        """Step 1: Read CSV file.

        Returns:
            DataFrame with raw data
        """
        logger.info("Step 1: Reading CSV from %s", self.input_path)
        start = time.time()

        self.df = self.spark.read.option("header", "true").csv(str(self.input_path))
        record_count = self.df.count()

        self.metrics["step_1_read"] = time.time() - start
        logger.info(
            "Step 1 completed in %.2fs - Read %d records",
            self.metrics["step_1_read"],
            record_count,
        )

        return self.df

    def step_2_transform(self):
        """Step 2: Transform data (type casting, cleaning).

        Returns:
            Transformed DataFrame
        """
        logger.info("Step 2: Transforming data")
        start = time.time()

        # Type casting
        self.df = self.df.withColumn(
            "timestamp", col("timestamp").cast(TimestampType())
        )

        # Cast string columns
        string_cols = [
            "event_id",
            "user_id",
            "session_id",
            "page_url",
            "country",
            "device_type",
            "ip_address",
        ]
        for col_name in string_cols:
            if col_name in self.df.columns:
                self.df = self.df.withColumn(col_name, col(col_name).cast(StringType()))

        # Basic cleaning - remove nulls in required columns
        self.df = self.df.filter(
            col("event_id").isNotNull()
            & col("user_id").isNotNull()
            & col("timestamp").isNotNull()
        )

        record_count = self.df.count()

        self.metrics["step_2_transform"] = time.time() - start
        logger.info(
            "Step 2 completed in %.2fs - %d records after cleaning",
            self.metrics["step_2_transform"],
            record_count,
        )

        return self.df

    def step_3_load(self, format: str = "parquet") -> Path:
        """Step 3: Load data to storage.

        Args:
            format: Output format (parquet, csv)

        Returns:
            Path to output directory
        """
        logger.info("Step 3: Loading data to %s", self.output_path)
        start = time.time()

        output_dir = self.output_path / f"output_{format}"

        if format == "parquet":
            self.df.coalesce(1).write.mode("overwrite").parquet(str(output_dir))
        elif format == "csv":
            self.df.coalesce(1).write.mode("overwrite").option("header", "true").csv(
                str(output_dir)
            )
        else:
            raise ValueError(f"Unsupported format: {format}")

        self.metrics["step_3_load"] = time.time() - start
        logger.info(
            "Step 3 completed in %.2fs - Wrote to %s",
            self.metrics["step_3_load"],
            output_dir,
        )

        return output_dir

    def step_4_merge(self, other_df, on: str = "user_id"):
        """Step 4: Merge with another dataset.

        Args:
            other_df: DataFrame to merge with
            on: Column to join on

        Returns:
            Merged DataFrame
        """
        logger.info("Step 4: Merging datasets on '%s'", on)
        start = time.time()

        self.df = self.df.join(other_df, on=on, how="left")
        record_count = self.df.count()

        self.metrics["step_4_merge"] = time.time() - start
        logger.info(
            "Step 4 completed in %.2fs - %d records after merge",
            self.metrics["step_4_merge"],
            record_count,
        )

        return self.df

    def step_5_additional(self):
        """Step 5: Additional features (aggregations, enrichment).

        Returns:
            DataFrame with additional features
        """
        logger.info("Step 5: Adding additional features")
        start = time.time()

        # Example: Add user aggregations
        user_stats = self.df.groupBy("user_id").agg(
            count("event_id").alias("total_events"),
            countDistinct("session_id").alias("total_sessions"),
        )

        self.df = self.df.join(user_stats, on="user_id", how="left")

        self.metrics["step_5_additional"] = time.time() - start
        logger.info("Step 5 completed in %.2fs", self.metrics["step_5_additional"])

        return self.df

    def run_pipeline(self, steps: int = 5) -> dict[str, Any]:
        """Run the complete pipeline up to specified step.

        Args:
            steps: Number of steps to run (1-5)

        Returns:
            Dictionary with metrics
        """
        logger.info("=" * 60)
        logger.info("Running Spark ETL Pipeline (Steps 1-%d)", steps)
        logger.info("=" * 60)

        total_start = time.time()

        # Step 1: Read
        self.step_1_read()

        if steps >= 2:
            # Step 2: Transform
            self.step_2_transform()

        if steps >= 3:
            # Step 3: Load
            self.step_3_load()

        if steps >= 4:
            # Step 4: Merge (skip if no merge data)
            logger.info("Step 4: Skipped (no merge data provided)")
            self.metrics["step_4_merge"] = 0.0

        if steps >= 5:
            # Step 5: Additional
            self.step_5_additional()

        total_time = time.time() - total_start

        logger.info("=" * 60)
        logger.info("Pipeline completed in %.2fs", total_time)
        logger.info("=" * 60)

        # Stop Spark
        self.spark.stop()

        return {
            "total_time": total_time,
            "steps": self.metrics,
            "records_processed": self.df.count() if self.df is not None else 0,
        }


def run_spark_etl(
    input_path: str = "data/input/sample_data.csv",
    output_path: str = "data/output/spark",
    steps: int = 5,
) -> dict[str, Any]:
    """Run Spark ETL pipeline.

    Args:
        input_path: Path to input CSV file
        output_path: Path to output directory
        steps: Number of steps to run (1-5)

    Returns:
        Dictionary with metrics
    """
    pipeline = SparkPipeline(input_path, output_path)
    return pipeline.run_pipeline(steps=steps)


if __name__ == "__main__":
    import sys

    # Allow running specific steps from command line
    steps = int(sys.argv[1]) if len(sys.argv) > 1 else 5

    metrics = run_spark_etl(steps=steps)

    print("\n" + "=" * 60)
    print("SPARK ETL METRICS")
    print("=" * 60)
    print(f"Total Time: {metrics['total_time']:.2f}s")
    print(f"Records Processed: {metrics['records_processed']:,}")
    print("\nStep Breakdown:")
    for step, duration in metrics["steps"].items():
        print(f"  {step}: {duration:.2f}s")
    print("=" * 60)
