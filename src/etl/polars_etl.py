"""Polars ETL - Incremental Pipeline Implementation

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

import polars as pl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PolarsPipeline:
    """Incremental ETL pipeline using Polars."""

    def __init__(self, input_path: str, output_path: str):
        """Initialize pipeline with input/output paths.

        Args:
            input_path (str): Path to input CSV file
            output_path (str): Path to output directory
        """
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.output_path.mkdir(parents=True, exist_ok=True)

        self.df = None
        self.metrics = {
            "step_1_read": 0.0,
            "step_2_transform": 0.0,
            "step_3_load": 0.0,
            "step_4_merge": 0.0,
            "step_5_additional": 0.0,
        }

    def step_1_read(self) -> pl.DataFrame:
        """Step 1: Read CSV file.

        Returns:
            DataFrame with raw data
        """
        logger.info("Step 1: Reading CSV from %s", self.input_path)
        start = time.time()

        self.df = pl.read_csv(self.input_path)

        self.metrics["step_1_read"] = time.time() - start
        logger.info(
            "Step 1 completed in %.2fs - Read %d records",
            self.metrics["step_1_read"],
            len(self.df),
        )

        return self.df

    def step_2_transform(self) -> pl.DataFrame:
        """Step 2: Transform data (type casting, cleaning).

        Returns:
            Transformed DataFrame
        """
        logger.info("Step 2: Transforming data")
        start = time.time()

        # Type casting
        self.df = self.df.with_columns(
            [pl.col("timestamp").str.to_datetime().alias("timestamp")]
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
        for col in string_cols:
            if col in self.df.columns:
                self.df = self.df.with_columns(
                    [pl.col(col).cast(pl.Utf8, strict=False).alias(col)]
                )

        # Basic cleaning - remove nulls in required columns
        self.df = self.df.filter(
            pl.col("event_id").is_not_null()
            & pl.col("user_id").is_not_null()
            & pl.col("timestamp").is_not_null()
        )

        self.metrics["step_2_transform"] = time.time() - start
        logger.info(
            "Step 2 completed in %.2fs - %d records after cleaning",
            self.metrics["step_2_transform"],
            len(self.df),
        )

        return self.df

    def step_3_load(self, format: str = "parquet") -> Path:
        """Step 3: Load data to storage.

        Args:
            format: Output format (parquet, csv)

        Returns:
            Path to output file

        Raises:
            ValueError: the format is not csv or parquet
        """
        logger.info("Step 3: Loading data to %s", self.output_path)
        start = time.time()

        output_file = self.output_path / f"output.{format}"

        if format == "parquet":
            self.df.write_parquet(output_file)
        elif format == "csv":
            self.df.write_csv(output_file)
        else:
            raise ValueError(f"Unsupported format: {format}")

        self.metrics["step_3_load"] = time.time() - start
        logger.info(
            "Step 3 completed in %.2fs - Wrote to %s",
            self.metrics["step_3_load"],
            output_file,
        )

        return output_file

    def step_4_merge(self, other_df: pl.DataFrame, on: str = "user_id") -> pl.DataFrame:
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

        self.metrics["step_4_merge"] = time.time() - start
        logger.info(
            "Step 4 completed in %.2fs - %d records after merge",
            self.metrics["step_4_merge"],
            len(self.df),
        )

        return self.df

    def step_5_additional(self) -> pl.DataFrame:
        """Step 5: Additional features (aggregations, enrichment).

        Returns:
            DataFrame with additional features
        """
        logger.info("Step 5: Adding additional features")
        start = time.time()

        # Example: Add user aggregations
        user_stats = self.df.group_by("user_id").agg([
            pl.count("event_id").alias("total_events"),
            pl.n_unique("session_id").alias("total_sessions"),
        ])

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
        logger.info("Running Polars ETL Pipeline (Steps 1-%d)", steps)
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

        return {
            "total_time": total_time,
            "steps": self.metrics,
            "records_processed": len(self.df) if self.df is not None else 0,
        }


def run_polars_etl(
    input_path: str = "data/input/sample_data.csv",
    output_path: str = "data/output/polars",
    steps: int = 5,
) -> dict[str, Any]:
    """Run Polars ETL pipeline.

    Args:
        input_path: Path to input CSV file
        output_path: Path to output directory
        steps: Number of steps to run (1-5)

    Returns:
        Dictionary with metrics
    """
    pipeline = PolarsPipeline(input_path, output_path)
    return pipeline.run_pipeline(steps=steps)


if __name__ == "__main__":
    import sys

    # Allow running specific steps from command line
    steps = int(sys.argv[1]) if len(sys.argv) > 1 else 5

    metrics = run_polars_etl(steps=steps)

    print("\n" + "=" * 60)
    print("POLARS ETL METRICS")
    print("=" * 60)
    print(f"Total Time: {metrics['total_time']:.2f}s")
    print(f"Records Processed: {metrics['records_processed']:,}")
    print("\nStep Breakdown:")
    for step, duration in metrics["steps"].items():
        print(f"  {step}: {duration:.2f}s")
    print("=" * 60)
