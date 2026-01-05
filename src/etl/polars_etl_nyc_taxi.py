"""Polars ETL for NYC Taxi dataset.

This module implements the ETL pipeline for NYC Taxi data using Polars,
designed for vertical scaling benchmarks on EC2.
"""

import argparse
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from src.etl.nyc_taxi_config import DataSize, get_dataset_config
from src.etl.nyc_taxi_data_access import NYCTaxiDataReader
from src.etl.timing_decorator import PipelineTimer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PolarsNYCTaxiETL:
    """ETL pipeline for NYC Taxi data using Polars."""

    def __init__(
        self,
        data_size: DataSize | str,
        output_path: str,
        output_bucket: str | None = None,
    ):
        """Initialize the ETL pipeline.

        Args:
            data_size: Size of dataset to process
            output_path: Local path for output files
            output_bucket: Optional S3 bucket for output (e.g., 's3://bucket-name')
        """
        self.data_size = data_size
        self.config = get_dataset_config(data_size)
        self.output_path = Path(output_path)
        self.output_path.mkdir(parents=True, exist_ok=True)
        self.output_bucket = output_bucket

        self.df = None
        self.timer = PipelineTimer(framework="polars", mode="nyc_taxi")

        logger.info("=" * 60)
        logger.info("Polars NYC Taxi ETL Pipeline")
        logger.info("=" * 60)
        logger.info("Dataset: %s (%s)", self.config.name, self.config.time_range)
        logger.info("Approx Size: %.2f GB", self.config.approx_size_gb)
        logger.info("Approx Records: %d", self.config.approx_records)
        logger.info("Output Path: %s", self.output_path)
        if self.output_bucket:
            logger.info("Output Bucket: %s", self.output_bucket)
        logger.info("=" * 60)

    def extract(self) -> pl.DataFrame:
        """Extract: Read data from NYC Taxi public S3 bucket.

        Returns:
            Raw DataFrame from S3
        """
        logger.info("EXTRACT: Reading NYC Taxi data from S3...")
        start = time.time()

        reader = NYCTaxiDataReader(self.config)
        self.df = reader.read_with_polars()

        elapsed = time.time() - start
        self.timer.metrics["extract"]["total"] = elapsed
        self.timer.sample_memory()

        logger.info(
            "Extract completed in %.2fs - %d records loaded", elapsed, len(self.df)
        )

        return self.df

    def transform(self) -> pl.DataFrame:
        """Transform: Filter, calculate metrics, and aggregate.

        Transformations:
        1. Filter invalid trips (passenger_count > 0, trip_distance > 0, fare > 0)
        2. Calculate price_per_mile = total_amount / trip_distance
        3. Extract date components (year, month, day, hour)
        4. Aggregate by pickup location and date

        Returns:
            Transformed DataFrame
        """
        logger.info("TRANSFORM: Applying transformations...")
        start = time.time()

        # Filter invalid trips
        logger.info("Filtering invalid trips...")
        initial_count = len(self.df)

        self.df = self.df.filter(
            (pl.col("passenger_count") > 0)
            & (pl.col("trip_distance") > 0)
            & (pl.col("fare_amount") > 0)
            & (pl.col("total_amount") > 0)
        )

        filtered_count = len(self.df)
        logger.info(
            "Filtered %d invalid records (%d remaining)",
            initial_count - filtered_count,
            filtered_count,
        )

        # Calculate price per mile
        logger.info("Calculating price_per_mile...")
        self.df = self.df.with_columns(
            (pl.col("total_amount") / pl.col("trip_distance")).alias("price_per_mile")
        )

        # Extract date (only, to match Spark ETL exactly)
        logger.info("Extracting date...")
        self.df = self.df.with_columns(
            pl.col("pickup_datetime").dt.date().alias("date")
        )

        # Handle nulls and outliers
        logger.info("Cleaning data...")
        # Remove extreme outliers (price_per_mile > $100 is likely an error)
        self.df = self.df.filter(pl.col("price_per_mile") < 100)

        # Aggregate by pickup location and date
        logger.info("Aggregating by location and date...")
        aggregated_df = self.df.group_by(["pickup_location_id", "date"]).agg([
            pl.col("fare_amount").mean().alias("avg_fare"),
            pl.col("trip_distance").mean().alias("avg_distance"),
            pl.col("price_per_mile").mean().alias("avg_price_per_mile"),
            pl.col("passenger_count").sum().alias("total_passengers"),
            pl.len().alias("trip_count"),
        ])

        # Sort by trip count descending
        aggregated_df = aggregated_df.sort("trip_count", descending=True)

        self.df = aggregated_df

        elapsed = time.time() - start
        self.timer.metrics["transform"]["total"] = elapsed
        self.timer.sample_memory()

        logger.info(
            "Transform completed in %.2fs - %d aggregated records",
            elapsed,
            len(self.df),
        )

        return self.df

    def load(self) -> dict[str, str]:
        """Load: Write results to output location.

        Writes:
        1. Aggregated results as Parquet
        2. Metadata JSON with execution metrics

        Returns:
            Dictionary with output file paths
        """
        logger.info("LOAD: Writing results...")
        start = time.time()

        # Prepare output filenames
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = (
            self.output_path / f"polars_nyc_taxi_{self.config.name}_{timestamp}.parquet"
        )
        metadata_file = (
            self.output_path / f"polars_nyc_taxi_{self.config.name}_{timestamp}.json"
        )

        # Write results to parquet
        logger.info("Writing results to %s", results_file)
        self.df.write_parquet(results_file)

        # If S3 bucket specified, also write there
        s3_results_path = None
        if self.output_bucket:
            s3_results_path = (
                f"{self.output_bucket}/polars/"
                f"{self.config.name}/results_{timestamp}.parquet"
            )
            logger.info("Writing results to S3: %s", s3_results_path)
            self.df.write_parquet(s3_results_path)

        # Prepare metadata
        metadata = {
            "framework": "polars",
            "dataset": self.config.name,
            "time_range": self.config.time_range,
            "execution_time": self.timer.metrics["total_time"],
            "record_count": len(self.df),
            "data_size_gb": self.config.approx_size_gb,
            "timestamp": timestamp,
            "output_file": str(results_file),
            "s3_output": s3_results_path,
            "metrics": self.timer.metrics,
        }

        # Write metadata
        logger.info("Writing metadata to %s", metadata_file)
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

        # If S3 bucket specified, also write metadata there
        if self.output_bucket:
            s3_metadata_path = (
                f"{self.output_bucket}/polars/"
                f"{self.config.name}/metadata_{timestamp}.json"
            )
            logger.info("Writing metadata to S3: %s", s3_metadata_path)
            # For S3, we'd use boto3 or s3fs here
            # For now, just log the path

        elapsed = time.time() - start
        self.timer.metrics["load"]["write"] = elapsed
        self.timer.metrics["load"]["total"] = elapsed
        self.timer.sample_memory()

        logger.info("Load completed in %.2fs", elapsed)

        return {
            "results_file": str(results_file),
            "metadata_file": str(metadata_file),
            "s3_results": s3_results_path,
        }

    def run(self) -> dict[str, Any]:
        """Run the complete ETL pipeline.

        Returns:
            Dictionary with execution results and metrics
        """
        logger.info("Starting Polars NYC Taxi ETL pipeline...")
        self.timer.start_pipeline()

        # Extract
        self.extract()

        # Transform
        self.transform()

        # Load
        output_paths = self.load()

        # Finalize timing
        self.timer.end_pipeline()

        logger.info("=" * 60)
        logger.info("Pipeline completed in %.2fs", self.timer.metrics["total_time"])
        logger.info("=" * 60)

        # Log timing summary
        self.timer.log_summary()

        return {
            "framework": "polars",
            "dataset": self.config.name,
            "total_time": self.timer.metrics["total_time"],
            "metrics": self.timer.metrics,
            "records_processed": len(self.df),
            "output_paths": output_paths,
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Polars ETL for NYC Taxi Dataset Benchmark"
    )
    parser.add_argument(
        "--size",
        type=str,
        default="tiny",
        choices=["tiny", "small", "medium", "large", "xlarge", "xxlarge"],
        help="Dataset size to process (default: tiny)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/output/nyc_taxi/polars",
        help="Output directory for results (default: data/output/nyc_taxi/polars)",
    )
    parser.add_argument(
        "--s3-bucket",
        type=str,
        help="Optional S3 bucket for output (e.g., s3://my-benchmark-bucket)",
    )

    args = parser.parse_args()

    # Run ETL
    etl = PolarsNYCTaxiETL(
        data_size=args.size, output_path=args.output, output_bucket=args.s3_bucket
    )

    start_time = datetime.now()
    results = etl.run()
    end_time = datetime.now()

    # Print summary
    print("\n" + "=" * 60)
    print("POLARS NYC TAXI ETL SUMMARY")
    print("=" * 60)
    print(f"Dataset: {results['dataset']}")
    print(f"Total Time: {results['total_time']:.2f}s")
    print(f"Records Processed: {results['records_processed']:,}")
    print(f"Output: {results['output_paths']['results_file']}")
    print("\nTiming Breakdown:")
    print(f"  Extract: {results['metrics']['extract']['total']:.2f}s")
    print(f"  Transform: {results['metrics']['transform']['total']:.2f}s")
    print(f"  Load: {results['metrics']['load']['total']:.2f}s")
    print("\nResource Usage:")
    print(f"  Peak Memory: {results['metrics']['resources']['peak_memory_mb']:.2f} MB")
    print(f"  Avg Memory: {results['metrics']['resources']['avg_memory_mb']:.2f} MB")
    print("=" * 60)
    print(f"Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Ended: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
