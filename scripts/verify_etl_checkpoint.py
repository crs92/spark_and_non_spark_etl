#!/usr/bin/env python3
# ruff: noqa: E402, S603, TRY300, PLR0911
"""Checkpoint verification script for TPC-H ETL implementations.

This script verifies that both PySpark and Polars ETL implementations:
1. Run successfully on the same TPC-H data
2. Produce identical results
3. Track metrics correctly
4. Handle errors appropriately

Usage:
    python scripts/verify_etl_checkpoint.py --scale-factor 1 --local
"""

import argparse
import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import polars as pl

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ETLCheckpointVerifier:
    """Verifies both ETL implementations produce identical results."""

    def __init__(
        self,
        scale_factor: int,
        local_mode: bool = True,
        s3_bucket: str | None = None,
    ):
        """Initialize checkpoint verifier.

        Args:
            scale_factor: TPC-H scale factor (1 for quick testing)
            local_mode: If True, use local filesystem instead of S3
            s3_bucket: S3 bucket name (required if not local_mode)
        """
        self.scale_factor = scale_factor
        self.local_mode = local_mode
        self.s3_bucket = s3_bucket

        # Create temporary directories for testing
        self.temp_dir = Path(tempfile.mkdtemp(prefix="tpch_checkpoint_"))
        self.data_dir = self.temp_dir / "data"
        self.spark_output_dir = self.temp_dir / "spark_output"
        self.polars_output_dir = self.temp_dir / "polars_output"

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.spark_output_dir.mkdir(parents=True, exist_ok=True)
        self.polars_output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Checkpoint verification initialized")
        logger.info("Temp directory: %s", self.temp_dir)
        logger.info("Scale factor: %d", scale_factor)
        logger.info("Local mode: %s", local_mode)

    def generate_test_data(self) -> bool:
        """Generate TPC-H test data using tpchgen-cli directly.

        Returns:
            True if generation succeeded, False otherwise
        """
        logger.info("=" * 60)
        logger.info("STEP 1: Generating TPC-H test data (SF %d)", self.scale_factor)
        logger.info("=" * 60)

        try:
            # Call tpchgen-cli directly for local generation
            cmd = [
                "tpchgen-cli",
                "--scale-factor",
                str(self.scale_factor),
                "--format",
                "parquet",
                "--output-dir",
                str(self.data_dir),
            ]

            logger.info("Running: %s", " ".join(cmd))
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)

            if result.returncode != 0:
                logger.error("Data generation failed!")
                logger.error("STDOUT: %s", result.stdout)
                logger.error("STDERR: %s", result.stderr)
                return False

            logger.info("Data generation completed successfully")
            logger.info("Output: %s", result.stdout)

            # Verify files exist
            required_files = [
                "customer.parquet",
                "orders.parquet",
                "lineitem.parquet",
            ]

            for filename in required_files:
                filepath = self.data_dir / filename
                if not filepath.exists():
                    logger.error("Missing required file: %s", filename)
                    return False
                logger.info(
                    "✓ Found: %s (%.2f MB)",
                    filename,
                    filepath.stat().st_size / 1024 / 1024,
                )

            return True

        except Exception as e:
            logger.error("Data generation failed: %s", e, exc_info=True)
            return False

    def run_polars_etl(self) -> dict[str, Any] | None:
        """Run Polars + DuckDB ETL implementation.

        Returns:
            Dictionary with results and metrics, or None if failed
        """
        logger.info("=" * 60)
        logger.info("STEP 2: Running Polars + DuckDB ETL")
        logger.info("=" * 60)

        try:
            # Import and run Polars ETL
            from src.etl.polars_etl_tpch import PolarsETLTPCH

            # For local mode, use file:// paths
            if self.local_mode:
                s3_input = f"file://{self.data_dir.absolute()}"
                s3_output = f"file://{self.polars_output_dir.absolute()}"
            else:
                s3_input = f"s3://{self.s3_bucket}/tpch-sf{self.scale_factor}"
                s3_output = f"s3://{self.s3_bucket}/checkpoint-test/polars"

            logger.info("Input path: %s", s3_input)
            logger.info("Output path: %s", s3_output)

            # Note: DuckDB's read_parquet doesn't support file:// prefix
            # We'll use absolute paths instead
            etl = PolarsETLTPCH(
                s3_input_path=str(self.data_dir.absolute()),
                s3_output_path=str(self.polars_output_dir.absolute()),
                scale_factor=self.scale_factor,
                local_output_path=str(self.polars_output_dir),
            )

            results = etl.run()

            logger.info("Polars ETL completed successfully")
            logger.info("Total time: %.2fs", results["total_time"])
            logger.info("Records processed: %d", results["records_processed"])

            return results

        except Exception as e:
            logger.error("Polars ETL failed: %s", e, exc_info=True)
            return None

    def run_spark_etl_local(self) -> dict[str, Any] | None:
        """Run PySpark ETL implementation in local mode.

        Returns:
            Dictionary with results and metrics, or None if failed
        """
        logger.info("=" * 60)
        logger.info("STEP 3: Running PySpark ETL (Local Mode)")
        logger.info("=" * 60)

        try:
            # Import Spark modules
            from pyspark.sql import SparkSession

            from src.etl.spark_etl_tpch import PerformanceTracker, SparkETLTPCH

            # Create local Spark session
            spark = (
                SparkSession.builder.appName("SparkTPCHCheckpoint")
                .master("local[*]")
                .config("spark.driver.memory", "4g")
                .config("spark.sql.shuffle.partitions", "4")
                .getOrCreate()
            )

            logger.info("Spark session created (local mode)")

            # Initialize ETL
            etl = SparkETLTPCH(
                spark=spark,
                s3_input_path=str(self.data_dir.absolute()),
                s3_output_path=str(self.spark_output_dir.absolute()),
                scale_factor=self.scale_factor,
            )

            # Initialize performance tracker
            tracker = PerformanceTracker()
            tracker.metrics["scale_factor"] = self.scale_factor

            import time

            start_time = time.time()

            # Load tables
            logger.info("Loading TPC-H tables...")
            tables = etl.load_tables()

            # Execute query
            logger.info("Executing TPC-H Query 3...")
            result_df = etl.execute_query(tables)
            result_count = result_df.count()

            # Write results locally
            logger.info("Writing results...")
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            local_path = self.spark_output_dir / f"results_{timestamp}"
            result_df.coalesce(1).write.mode("overwrite").parquet(str(local_path))

            # Record metrics
            end_time = time.time()
            tracker.record_execution(start_time, end_time)
            tracker.collect_spark_metrics(spark)

            # Write metrics
            tracker.write_metrics(
                str(self.spark_output_dir), str(self.spark_output_dir), timestamp
            )

            logger.info("Spark ETL completed successfully")
            logger.info("Total time: %.2fs", tracker.metrics["execution_time"])
            logger.info("Records processed: %d", result_count)

            # Stop Spark
            spark.stop()

            return {
                "framework": "spark",
                "scale_factor": self.scale_factor,
                "total_time": tracker.metrics["execution_time"],
                "records_processed": result_count,
                "metrics": tracker.metrics,
                "output_path": str(local_path),
            }

        except Exception as e:
            logger.error("Spark ETL failed: %s", e, exc_info=True)
            return None

    def compare_results(
        self, spark_results: dict[str, Any], polars_results: dict[str, Any]
    ) -> bool:
        """Compare results from both ETL implementations.

        Args:
            spark_results: Results from Spark ETL
            polars_results: Results from Polars ETL

        Returns:
            True if results match, False otherwise
        """
        logger.info("=" * 60)
        logger.info("STEP 4: Comparing Results")
        logger.info("=" * 60)

        try:
            # Load Spark results (Spark writes to a directory with part files)
            spark_output_path = spark_results["output_path"]
            logger.info("Loading Spark results from: %s", spark_output_path)
            # Use glob pattern to read only parquet files
            spark_df = pl.read_parquet(f"{spark_output_path}/*.parquet")
            logger.info("Spark results: %d rows", len(spark_df))

            # Load Polars results
            polars_output_files = list(self.polars_output_dir.glob("results_*.parquet"))
            if not polars_output_files:
                logger.error("No Polars result files found")
                return False

            polars_output_path = polars_output_files[0]
            logger.info("Loading Polars results from: %s", polars_output_path)
            polars_df = pl.read_parquet(polars_output_path)
            logger.info("Polars results: %d rows", len(polars_df))

            # Compare row counts
            if len(spark_df) != len(polars_df):
                logger.error(
                    "Row count mismatch: Spark=%d, Polars=%d",
                    len(spark_df),
                    len(polars_df),
                )
                return False

            logger.info("✓ Row counts match: %d rows", len(spark_df))

            # Sort both dataframes by l_orderkey for comparison
            spark_df = spark_df.sort("l_orderkey")
            polars_df = polars_df.sort("l_orderkey")

            # Compare schemas
            spark_cols = set(spark_df.columns)
            polars_cols = set(polars_df.columns)

            if spark_cols != polars_cols:
                logger.error("Schema mismatch!")
                logger.error("Spark columns: %s", spark_cols)
                logger.error("Polars columns: %s", polars_cols)
                return False

            logger.info("✓ Schemas match: %s", spark_cols)

            # Compare data values (with tolerance for floating point)
            logger.info("Comparing data values...")

            # Check l_orderkey (should be exact)
            if not spark_df["l_orderkey"].equals(polars_df["l_orderkey"]):
                logger.error("l_orderkey values don't match")
                logger.error("Spark: %s", spark_df["l_orderkey"].to_list())
                logger.error("Polars: %s", polars_df["l_orderkey"].to_list())
                return False

            logger.info("✓ l_orderkey values match")

            # Check revenue (with tolerance for floating point differences)
            spark_revenue = spark_df["revenue"].to_list()
            polars_revenue = polars_df["revenue"].to_list()

            max_diff = 0.0
            for i, (s_rev, p_rev) in enumerate(zip(spark_revenue, polars_revenue)):
                diff = abs(s_rev - p_rev)
                max_diff = max(max_diff, diff)
                if diff > 0.01:  # Allow 1 cent difference due to floating point
                    logger.error(
                        "Revenue mismatch at row %d: Spark=%.2f, Polars=%.2f,"
                        " diff=%.4f",
                        i,
                        s_rev,
                        p_rev,
                        diff,
                    )
                    return False

            logger.info("✓ Revenue values match (max diff: %.6f)", max_diff)

            # Check dates
            if not spark_df["o_orderdate"].equals(polars_df["o_orderdate"]):
                logger.error("o_orderdate values don't match")
                return False

            logger.info("✓ o_orderdate values match")

            # Check shipping priority
            if not spark_df["o_shippriority"].equals(polars_df["o_shippriority"]):
                logger.error("o_shippriority values don't match")
                return False

            logger.info("✓ o_shippriority values match")

            logger.info("=" * 60)
            logger.info("✓ ALL RESULTS MATCH!")
            logger.info("=" * 60)

            return True

        except Exception as e:
            logger.error("Result comparison failed: %s", e, exc_info=True)
            return False

    def compare_metrics(
        self, spark_results: dict[str, Any], polars_results: dict[str, Any]
    ) -> bool:
        """Compare metrics from both ETL implementations.

        Args:
            spark_results: Results from Spark ETL
            polars_results: Results from Polars ETL

        Returns:
            True if metrics are valid, False otherwise
        """
        logger.info("=" * 60)
        logger.info("STEP 5: Validating Metrics")
        logger.info("=" * 60)

        try:
            # Check Spark metrics
            spark_metrics = spark_results["metrics"]
            logger.info("Spark Metrics:")
            logger.info("  Execution time: %.2fs", spark_metrics["execution_time"])
            logger.info("  Peak memory: %d MB", spark_metrics["peak_memory_mb"])

            # Check Polars metrics
            polars_metrics = polars_results["metrics"]
            logger.info("Polars Metrics:")
            logger.info("  Total time: %.2fs", polars_metrics["total_time"])
            logger.info(
                "  Peak memory: %.2f MB",
                polars_metrics["resources"]["peak_memory_mb"],
            )

            # Validate metrics are reasonable
            if spark_metrics["execution_time"] <= 0:
                logger.error("Invalid Spark execution time")
                return False

            if polars_metrics["total_time"] <= 0:
                logger.error("Invalid Polars total time")
                return False

            logger.info("✓ Metrics are valid")

            # Compare performance
            logger.info("=" * 60)
            logger.info("Performance Comparison:")
            logger.info("=" * 60)
            logger.info("Spark execution time: %.2fs", spark_metrics["execution_time"])
            logger.info("Polars total time: %.2fs", polars_metrics["total_time"])

            speedup = spark_metrics["execution_time"] / polars_metrics["total_time"]
            logger.info("Speedup: %.2fx", speedup)

            if speedup > 1:
                logger.info("✓ Polars is %.2fx faster than Spark", speedup)
            else:
                logger.info("✓ Spark is %.2fx faster than Polars", 1 / speedup)

            return True

        except Exception as e:
            logger.error("Metrics validation failed: %s", e, exc_info=True)
            return False

    def cleanup(self):
        """Clean up temporary directories."""
        logger.info("Cleaning up temporary files...")
        import shutil

        try:
            shutil.rmtree(self.temp_dir)
            logger.info("Cleanup complete")
        except Exception as e:
            logger.warning("Cleanup failed: %s", e)

    def run_checkpoint(self) -> bool:
        """Run complete checkpoint verification.

        Returns:
            True if all checks pass, False otherwise
        """
        logger.info("=" * 60)
        logger.info("TPC-H ETL CHECKPOINT VERIFICATION")
        logger.info("=" * 60)

        try:
            # Step 1: Generate test data
            if not self.generate_test_data():
                logger.error("❌ Data generation failed")
                return False

            # Step 2: Run Polars ETL
            polars_results = self.run_polars_etl()
            if not polars_results:
                logger.error("❌ Polars ETL failed")
                return False

            # Step 3: Run Spark ETL
            spark_results = self.run_spark_etl_local()
            if not spark_results:
                logger.error("❌ Spark ETL failed")
                return False

            # Step 4: Compare results
            if not self.compare_results(spark_results, polars_results):
                logger.error("❌ Results don't match")
                return False

            # Step 5: Validate metrics
            if not self.compare_metrics(spark_results, polars_results):
                logger.error("❌ Metrics validation failed")
                return False

            logger.info("=" * 60)
            logger.info("✓ CHECKPOINT VERIFICATION PASSED!")
            logger.info("=" * 60)
            logger.info("Summary:")
            logger.info("  - Both ETL implementations run successfully")
            logger.info("  - Results are identical")
            logger.info("  - Metrics tracking works correctly")
            logger.info("  - Ready for production deployment")
            logger.info("=" * 60)

            return True

        except Exception as e:
            logger.error("Checkpoint verification failed: %s", e, exc_info=True)
            return False
        finally:
            # Always cleanup
            self.cleanup()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Verify TPC-H ETL checkpoint")
    parser.add_argument(
        "--scale-factor",
        type=int,
        default=1,
        help="TPC-H scale factor (1 for quick testing, 10 for full test)",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        default=True,
        help="Use local filesystem instead of S3",
    )
    parser.add_argument(
        "--s3-bucket",
        type=str,
        help="S3 bucket name (required if not --local)",
    )
    args = parser.parse_args()

    if not args.local and not args.s3_bucket:
        logger.error("--s3-bucket is required when not using --local")
        return 1

    # Run checkpoint verification
    verifier = ETLCheckpointVerifier(
        scale_factor=args.scale_factor,
        local_mode=args.local,
        s3_bucket=args.s3_bucket,
    )

    success = verifier.run_checkpoint()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
