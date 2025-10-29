#!/usr/bin/env python3
"""Complete ETL Benchmark Script - Bulk + Incremental Processing

This script runs a comprehensive benchmark comparing Spark and Polars ETL stacks
across both bulk and incremental processing modes.

Features:
- Bulk data processing (30 days historical)
- Incremental data processing (7 days daily files)
- Performance metrics collection
- Comparative analysis and reporting
- JSON results export
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.etl.polars_etl import run_polars_etl
from src.etl.spark_etl import run_spark_etl

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class FullETLBenchmark:
    """Complete ETL benchmark runner for bulk + incremental processing."""

    def __init__(
        self,
        data_size: str = "small",
        output_dir: str = "benchmark_results",
        use_iceberg: bool = False,
    ):
        """Initialize benchmark.

        Args:
            data_size: Size of test data (small, medium, large)
            output_dir: Directory to save results
            use_iceberg: Whether to use Iceberg tables (default: False for fair comparison)
        """
        self.data_size = data_size
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.use_iceberg = use_iceberg

        self.results = {
            "metadata": {
                "data_size": data_size,
                "timestamp": datetime.now().isoformat(),
                "use_iceberg": use_iceberg,
            },
            "polars": {},
            "spark": {},
            "comparison": {},
        }

    def run_bulk_processing(self, framework: str) -> dict[str, Any]:
        """Run bulk processing for a framework.

        Args:
            framework: Framework name ('polars' or 'spark')

        Returns:
            Dictionary with bulk processing results
        """
        logger.info("=" * 80)
        logger.info(f"Running {framework.upper()} - BULK Processing")
        logger.info("=" * 80)

        input_path = f"data/generated/bulk/bulk_data_{self.data_size}.parquet"
        output_path = f"data/output/{framework}"

        # Check if input file exists
        if not Path(input_path).exists():
            logger.error(f"Input file not found: {input_path}")
            logger.info("Please run: make generate-data-full SIZE=%s", self.data_size)
            raise FileNotFoundError(f"Input file not found: {input_path}")

        start_time = time.time()

        if framework == "polars":
            results = run_polars_etl(
                input_path=input_path,
                output_path=output_path,
                mode="bulk",
                output_format="parquet",
                use_iceberg=self.use_iceberg,
            )
        else:  # spark
            results = run_spark_etl(
                input_path=input_path,
                output_path=output_path,
                mode="bulk",
                use_iceberg=self.use_iceberg,
            )

        results["wall_clock_time"] = time.time() - start_time

        logger.info(
            f"{framework.upper()} bulk processing completed in"
            f" {results['wall_clock_time']:.2f}s"
        )

        return results

    def run_incremental_processing(self, framework: str) -> dict[str, Any]:
        """Run incremental processing for a framework.

        Args:
            framework: Framework name ('polars' or 'spark')

        Returns:
            Dictionary with incremental processing results
        """
        logger.info("=" * 80)
        logger.info(f"Running {framework.upper()} - INCREMENTAL Processing")
        logger.info("=" * 80)

        input_path = "data/generated/incremental"
        output_path = f"data/output/{framework}"
        bulk_data_path = f"data/output/{framework}/{framework}_output_bulk.parquet"

        # Check if input directory exists
        if not Path(input_path).exists():
            logger.error(f"Input directory not found: {input_path}")
            logger.info("Please run: make generate-data-full SIZE=%s", self.data_size)
            raise FileNotFoundError(f"Input directory not found: {input_path}")

        # Check if bulk data exists
        if not Path(bulk_data_path).exists():
            logger.error(f"Bulk data not found: {bulk_data_path}")
            logger.info("Please run bulk processing first")
            raise FileNotFoundError(f"Bulk data not found: {bulk_data_path}")

        start_time = time.time()

        if framework == "polars":
            results = run_polars_etl(
                input_path=input_path,
                output_path=output_path,
                mode="incremental",
                output_format="parquet",
                bulk_data_path=bulk_data_path if not self.use_iceberg else None,
                use_iceberg=self.use_iceberg,
            )
        else:  # spark
            results = run_spark_etl(
                input_path=input_path,
                output_path=output_path,
                mode="incremental",
                bulk_data_path=bulk_data_path if not self.use_iceberg else None,
                use_iceberg=self.use_iceberg,
            )

        results["wall_clock_time"] = time.time() - start_time

        logger.info(
            f"{framework.upper()} incremental processing completed in"
            f" {results['wall_clock_time']:.2f}s"
        )

        return results

    def run_framework_benchmark(self, framework: str) -> dict[str, Any]:
        """Run complete benchmark for a framework (bulk + incremental).

        Args:
            framework: Framework name ('polars' or 'spark')

        Returns:
            Dictionary with complete framework results
        """
        logger.info("\n" + "=" * 80)
        logger.info(f"BENCHMARKING {framework.upper()} STACK")
        logger.info("=" * 80)

        framework_start = time.time()

        # Run bulk processing
        bulk_results = self.run_bulk_processing(framework)

        # Run incremental processing
        incremental_results = self.run_incremental_processing(framework)

        total_time = time.time() - framework_start

        return {
            "bulk": bulk_results,
            "incremental": incremental_results,
            "total_time": total_time,
        }

    def run_complete_benchmark(self) -> dict[str, Any]:
        """Run complete benchmark for both frameworks.

        Returns:
            Dictionary with all benchmark results
        """
        logger.info("\n" + "=" * 80)
        logger.info("COMPLETE ETL BENCHMARK - BULK + INCREMENTAL")
        logger.info("=" * 80)
        logger.info(f"Data Size: {self.data_size}")
        logger.info(f"Timestamp: {self.results['metadata']['timestamp']}")
        logger.info("=" * 80)

        benchmark_start = time.time()

        # Run Polars benchmark
        try:
            self.results["polars"] = self.run_framework_benchmark("polars")
        except Exception as e:
            logger.error(f"Polars benchmark failed: {e}")
            self.results["polars"] = {"error": str(e)}

        # Run Spark benchmark
        try:
            self.results["spark"] = self.run_framework_benchmark("spark")
        except Exception as e:
            logger.error(f"Spark benchmark failed: {e}")
            self.results["spark"] = {"error": str(e)}

        self.results["metadata"]["total_benchmark_time"] = time.time() - benchmark_start

        # Generate comparison
        self.generate_comparison()

        return self.results

    def generate_comparison(self):
        """Generate comparative analysis between frameworks."""
        logger.info("\n" + "=" * 80)
        logger.info("GENERATING COMPARISON ANALYSIS")
        logger.info("=" * 80)

        polars = self.results.get("polars", {})
        spark = self.results.get("spark", {})

        if "error" in polars or "error" in spark:
            logger.warning("Cannot generate comparison due to errors")
            self.results["comparison"] = {"error": "One or more frameworks failed"}
            return

        comparison = {
            "bulk_processing": {},
            "incremental_processing": {},
            "total_performance": {},
        }

        # Bulk processing comparison
        if "bulk" in polars and "bulk" in spark:
            polars_bulk_time = polars["bulk"]["total_time"]
            spark_bulk_time = spark["bulk"]["total_time"]

            comparison["bulk_processing"] = {
                "polars_time": polars_bulk_time,
                "spark_time": spark_bulk_time,
                "winner": "polars" if polars_bulk_time < spark_bulk_time else "spark",
                "speedup": (
                    spark_bulk_time / polars_bulk_time
                    if polars_bulk_time < spark_bulk_time
                    else polars_bulk_time / spark_bulk_time
                ),
                "advantage_pct": (
                    abs(spark_bulk_time - polars_bulk_time)
                    / max(spark_bulk_time, polars_bulk_time)
                    * 100
                ),
            }

        # Incremental processing comparison
        if "incremental" in polars and "incremental" in spark:
            polars_incr_time = polars["incremental"]["total_time"]
            spark_incr_time = spark["incremental"]["total_time"]

            comparison["incremental_processing"] = {
                "polars_time": polars_incr_time,
                "spark_time": spark_incr_time,
                "winner": "polars" if polars_incr_time < spark_incr_time else "spark",
                "speedup": (
                    spark_incr_time / polars_incr_time
                    if polars_incr_time < spark_incr_time
                    else polars_incr_time / spark_incr_time
                ),
                "advantage_pct": (
                    abs(spark_incr_time - polars_incr_time)
                    / max(spark_incr_time, polars_incr_time)
                    * 100
                ),
            }

        # Total performance comparison
        polars_total = polars.get("total_time", 0)
        spark_total = spark.get("total_time", 0)

        comparison["total_performance"] = {
            "polars_total_time": polars_total,
            "spark_total_time": spark_total,
            "winner": "polars" if polars_total < spark_total else "spark",
            "speedup": (
                spark_total / polars_total
                if polars_total < spark_total
                else polars_total / spark_total
            ),
            "advantage_pct": (
                abs(spark_total - polars_total) / max(spark_total, polars_total) * 100
            ),
        }

        self.results["comparison"] = comparison

    def print_results(self):
        """Print formatted benchmark results."""
        print("\n" + "=" * 80)
        print("COMPLETE ETL BENCHMARK RESULTS")
        print("=" * 80)
        print(f"Data Size: {self.data_size}")
        print(f"Timestamp: {self.results['metadata']['timestamp']}")
        print("=" * 80)

        polars = self.results.get("polars", {})
        spark = self.results.get("spark", {})
        comparison = self.results.get("comparison", {})

        if "error" in polars or "error" in spark:
            print("\n⚠️  ERRORS OCCURRED:")
            if "error" in polars:
                print(f"  Polars: {polars['error']}")
            if "error" in spark:
                print(f"  Spark: {spark['error']}")
            return

        # Bulk processing results
        print("\n" + "-" * 80)
        print("BULK PROCESSING (30 days historical data)")
        print("-" * 80)
        print(f"{'Metric':<40} {'Polars':<20} {'Spark':<20}")
        print("-" * 80)

        if "bulk" in polars and "bulk" in spark:
            print(
                f"{'Total Time (s)':<40} {polars['bulk']['total_time']:<20.2f} {spark['bulk']['total_time']:<20.2f}"
            )
            print(
                f"{'Records Processed':<40} {polars['bulk']['records_processed']:<20,} {spark['bulk']['records_processed']:<20,}"
            )

            bulk_comp = comparison.get("bulk_processing", {})
            if bulk_comp:
                winner = bulk_comp["winner"].upper()
                speedup = bulk_comp["speedup"]
                advantage = bulk_comp["advantage_pct"]
                print(
                    f"\n✓ Winner: {winner} ({speedup:.2f}x faster, {advantage:.1f}%"
                    " advantage)"
                )

        # Incremental processing results
        print("\n" + "-" * 80)
        print("INCREMENTAL PROCESSING (7 days daily files + merge)")
        print("-" * 80)
        print(f"{'Metric':<40} {'Polars':<20} {'Spark':<20}")
        print("-" * 80)

        if "incremental" in polars and "incremental" in spark:
            print(
                f"{'Total Time (s)':<40} {polars['incremental']['total_time']:<20.2f} {spark['incremental']['total_time']:<20.2f}"
            )
            print(
                f"{'Records Processed':<40} {polars['incremental']['records_processed']:<20,} {spark['incremental']['records_processed']:<20,}"
            )

            incr_comp = comparison.get("incremental_processing", {})
            if incr_comp:
                winner = incr_comp["winner"].upper()
                speedup = incr_comp["speedup"]
                advantage = incr_comp["advantage_pct"]
                print(
                    f"\n✓ Winner: {winner} ({speedup:.2f}x faster, {advantage:.1f}%"
                    " advantage)"
                )

        # Total performance
        print("\n" + "-" * 80)
        print("TOTAL PERFORMANCE (Bulk + Incremental)")
        print("-" * 80)
        print(f"{'Framework':<40} {'Total Time (s)':<20}")
        print("-" * 80)
        print(f"{'Polars':<40} {polars.get('total_time', 0):<20.2f}")
        print(f"{'Spark':<40} {spark.get('total_time', 0):<20.2f}")

        total_comp = comparison.get("total_performance", {})
        if total_comp:
            winner = total_comp["winner"].upper()
            speedup = total_comp["speedup"]
            advantage = total_comp["advantage_pct"]
            print(
                f"\n✓ Overall Winner: {winner} ({speedup:.2f}x faster, {advantage:.1f}%"
                " advantage)"
            )

        print("\n" + "=" * 80)

    def save_results(self):
        """Save benchmark results to JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.output_dir / f"benchmark_full_{self.data_size}_{timestamp}.json"

        # Convert quality reports to dict for JSON serialization
        def convert_to_serializable(obj):
            if hasattr(obj, "__dict__"):
                return obj.__dict__
            return str(obj)

        with open(filename, "w") as f:
            json.dump(self.results, f, indent=2, default=convert_to_serializable)

        logger.info(f"Results saved to: {filename}")
        return filename


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Complete ETL Benchmark - Bulk + Incremental Processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run benchmark with small dataset
  python scripts/benchmark_full.py --size small

  # Run benchmark with medium dataset
  python scripts/benchmark_full.py --size medium

  # Specify custom output directory
  python scripts/benchmark_full.py --size small --output results/

Prerequisites:
  1. Generate test data first:
     make generate-data-full SIZE=small

  2. Ensure output directories exist:
     mkdir -p data/output/polars data/output/spark
        """,
    )

    parser.add_argument(
        "--size",
        choices=["small", "medium", "large"],
        default="small",
        help="Size of test dataset (default: small)",
    )
    parser.add_argument(
        "--output",
        default="benchmark_results",
        help="Output directory for results (default: benchmark_results)",
    )
    parser.add_argument(
        "--use-iceberg",
        action="store_true",
        help=(
            "Use Iceberg tables instead of Parquet files (default: False for"
            " benchmarking)"
        ),
    )

    args = parser.parse_args()

    # Run benchmark
    benchmark = FullETLBenchmark(
        data_size=args.size,
        output_dir=args.output,
        use_iceberg=args.use_iceberg,
    )

    try:
        benchmark.run_complete_benchmark()
        benchmark.print_results()
        results_file = benchmark.save_results()

        print("\n✅ Benchmark completed successfully!")
        print(f"📊 Results saved to: {results_file}")

    except Exception as e:
        logger.error(f"Benchmark failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
