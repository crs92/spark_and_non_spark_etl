"""Spark ETL for NYC Taxi dataset.

This module implements the ETL pipeline for NYC Taxi data using PySpark,
designed for horizontal scaling benchmarks on EKS.
"""

import argparse
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    avg,
    col,
    count,
    dayofmonth,
    hour,
    month,
    to_date,
    year,
)
from pyspark.sql.functions import (
    sum as spark_sum,
)

from src.etl.nyc_taxi_config import DataSize, get_dataset_config
from src.etl.timing_decorator import PipelineTimer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SparkNYCTaxiETL:
    """ETL pipeline for NYC Taxi data using PySpark."""

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

        self.spark = None
        self.df = None
        self.timer = PipelineTimer(framework="spark", mode="nyc_taxi")

        logger.info("=" * 60)
        logger.info("Spark NYC Taxi ETL Pipeline")
        logger.info("=" * 60)
        logger.info("Dataset: %s (%s)", self.config.name, self.config.time_range)
        logger.info("Approx Size: %.2f GB", self.config.approx_size_gb)
        logger.info("Approx Records: %d", self.config.approx_records)
        logger.info("Output Path: %s", self.output_path)
        if self.output_bucket:
            logger.info("Output Bucket: %s", self.output_bucket)
        logger.info("=" * 60)

        self._init_spark()

    def _init_spark(self):
        """Initialize Spark session with appropriate configuration."""
        logger.info("Initializing Spark session...")
        start = time.time()

        spark_builder = (
            SparkSession.builder.appName("SparkNYCTaxiETL")
            .config("spark.sql.adaptive.enabled", "true")
            .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
            .config("spark.sql.adaptive.advisoryPartitionSizeInBytes", "128MB")
        )

        # Configure for S3 access
        spark_builder = (
            spark_builder.config(
                "spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem"
            )
            .config(
                "spark.hadoop.fs.s3a.aws.credentials.provider",
                "com.amazonaws.auth.DefaultAWSCredentialsProviderChain",
            )
            .config("spark.hadoop.fs.s3a.endpoint", "s3.amazonaws.com")
        )

        # Check if running in Kubernetes (distributed mode)
        if os.getenv("SPARK_MASTER_URL", "").startswith("k8s://"):
            logger.info("Configuring Spark for Kubernetes distributed processing")
            spark_builder = (
                spark_builder.config("spark.master", os.getenv("SPARK_MASTER_URL"))
                .config(
                    "spark.executor.instances",
                    os.getenv("SPARK_EXECUTOR_INSTANCES", "3"),
                )
                .config(
                    "spark.executor.memory",
                    os.getenv("SPARK_EXECUTOR_MEMORY", "8g"),
                )
                .config(
                    "spark.executor.cores",
                    os.getenv("SPARK_EXECUTOR_CORES", "4"),
                )
                .config("spark.kubernetes.container.image", "spark-etl:latest")
                .config("spark.kubernetes.namespace", "default")
            )
        else:
            logger.info("Configuring Spark for local processing")
            spark_builder = spark_builder.master("local[*]")

        self.spark = spark_builder.getOrCreate()

        elapsed = time.time() - start
        self.timer.metrics["startup_time"] = elapsed

        logger.info("Spark Master: %s", self.spark.sparkContext.master)
        logger.info("Spark initialization took %.2fs", elapsed)

    def extract(self):
        """Extract: Read data from NYC Taxi public S3 bucket.

        Returns:
            Spark DataFrame from S3
        """
        logger.info("EXTRACT: Reading NYC Taxi data from S3...")
        start = time.time()

        # Get list of files to read
        files = self.config.get_file_list()
        logger.info("Reading %d files from S3...", len(files))

        # Convert s3:// to s3a:// for Spark
        s3a_files = [f.replace("s3://", "s3a://") for f in files]

        # Read all files
        # Note: Spark will handle missing files gracefully
        try:
            self.df = self.spark.read.parquet(*s3a_files)
            record_count = self.df.count()
            logger.info("Successfully read %d records", record_count)
        except Exception as e:
            logger.error("Failed to read data: %s", e)
            raise

        elapsed = time.time() - start
        self.timer.metrics["extract"]["total"] = elapsed
        self.timer.sample_memory()

        logger.info("Extract completed in %.2fs", elapsed)

        return self.df

    def transform(self):
        """Transform: Filter, calculate metrics, and aggregate.

        Transformations:
        1. Standardize schema (handle column name variations)
        2. Filter invalid trips (passenger_count > 0, trip_distance > 0, fare > 0)
        3. Calculate price_per_mile = total_amount / trip_distance
        4. Extract date components (year, month, day, hour)
        5. Aggregate by pickup location and date

        Returns:
            Transformed Spark DataFrame
        """
        logger.info("TRANSFORM: Applying transformations...")
        start = time.time()

        # Standardize schema - handle different column names across years
        logger.info("Standardizing schema...")
        column_mapping = {
            "tpep_pickup_datetime": "pickup_datetime",
            "tpep_dropoff_datetime": "dropoff_datetime",
            "PULocationID": "pickup_location_id",
            "DOLocationID": "dropoff_location_id",
        }

        for old_col, new_col in column_mapping.items():
            if old_col in self.df.columns:
                self.df = self.df.withColumnRenamed(old_col, new_col)

        # Filter invalid trips
        logger.info("Filtering invalid trips...")
        initial_count = self.df.count()

        self.df = self.df.filter(
            (col("passenger_count") > 0)
            & (col("trip_distance") > 0)
            & (col("fare_amount") > 0)
            & (col("total_amount") > 0)
        )

        filtered_count = self.df.count()
        logger.info(
            "Filtered %d invalid records (%d remaining)",
            initial_count - filtered_count,
            filtered_count,
        )

        # Calculate price per mile
        logger.info("Calculating price_per_mile...")
        self.df = self.df.withColumn(
            "price_per_mile", col("total_amount") / col("trip_distance")
        )

        # Extract date components
        logger.info("Extracting date components...")
        self.df = (
            self.df.withColumn("year", year(col("pickup_datetime")))
            .withColumn("month", month(col("pickup_datetime")))
            .withColumn("day", dayofmonth(col("pickup_datetime")))
            .withColumn("hour", hour(col("pickup_datetime")))
            .withColumn("date", to_date(col("pickup_datetime")))
        )

        # Handle nulls and outliers
        logger.info("Cleaning data...")
        # Remove extreme outliers (price_per_mile > $100 is likely an error)
        self.df = self.df.filter(col("price_per_mile") < 100)

        # Aggregate by pickup location and date
        logger.info("Aggregating by location and date...")
        aggregated_df = self.df.groupBy("pickup_location_id", "date").agg(
            avg("fare_amount").alias("avg_fare"),
            avg("trip_distance").alias("avg_distance"),
            avg("price_per_mile").alias("avg_price_per_mile"),
            spark_sum("passenger_count").alias("total_passengers"),
            count("*").alias("trip_count"),
        )

        # Sort by trip count descending
        aggregated_df = aggregated_df.orderBy(col("trip_count").desc())

        self.df = aggregated_df

        elapsed = time.time() - start
        self.timer.metrics["transform"]["total"] = elapsed
        self.timer.sample_memory()

        logger.info(
            "Transform completed in %.2fs - %d aggregated records",
            elapsed,
            self.df.count(),
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
        results_dir = (
            self.output_path / f"spark_nyc_taxi_{self.config.name}_{timestamp}"
        )
        metadata_file = (
            self.output_path / f"spark_nyc_taxi_{self.config.name}_{timestamp}.json"
        )

        # Write results to parquet
        logger.info("Writing results to %s", results_dir)
        self.df.coalesce(1).write.mode("overwrite").parquet(str(results_dir))

        # If S3 bucket specified, also write there
        s3_results_path = None
        if self.output_bucket:
            s3_results_path = (
                f"{self.output_bucket}/spark/{self.config.name}/results_{timestamp}"
            )
            # Convert to s3a:// for Spark
            s3a_path = s3_results_path.replace("s3://", "s3a://")
            logger.info("Writing results to S3: %s", s3_results_path)
            self.df.coalesce(1).write.mode("overwrite").parquet(s3a_path)

        # Prepare metadata
        metadata = {
            "framework": "spark",
            "dataset": self.config.name,
            "time_range": self.config.time_range,
            "execution_time": self.timer.metrics["total_time"],
            "record_count": self.df.count(),
            "data_size_gb": self.config.approx_size_gb,
            "timestamp": timestamp,
            "output_dir": str(results_dir),
            "s3_output": s3_results_path,
            "metrics": self.timer.metrics,
            "spark_config": {
                "master": self.spark.sparkContext.master,
                "app_name": self.spark.sparkContext.appName,
            },
        }

        # Write metadata
        logger.info("Writing metadata to %s", metadata_file)
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

        elapsed = time.time() - start
        self.timer.metrics["load"]["write"] = elapsed
        self.timer.metrics["load"]["total"] = elapsed
        self.timer.sample_memory()

        logger.info("Load completed in %.2fs", elapsed)

        return {
            "results_dir": str(results_dir),
            "metadata_file": str(metadata_file),
            "s3_results": s3_results_path,
        }

    def run(self) -> dict[str, Any]:
        """Run the complete ETL pipeline.

        Returns:
            Dictionary with execution results and metrics
        """
        logger.info("Starting Spark NYC Taxi ETL pipeline...")
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

        # Stop Spark
        self.spark.stop()

        return {
            "framework": "spark",
            "dataset": self.config.name,
            "total_time": self.timer.metrics["total_time"],
            "metrics": self.timer.metrics,
            "records_processed": self.df.count() if self.df else 0,
            "output_paths": output_paths,
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Spark ETL for NYC Taxi Dataset Benchmark"
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
        default="data/output/nyc_taxi/spark",
        help="Output directory for results (default: data/output/nyc_taxi/spark)",
    )
    parser.add_argument(
        "--s3-bucket",
        type=str,
        help="Optional S3 bucket for output (e.g., s3://my-benchmark-bucket)",
    )

    args = parser.parse_args()

    # Run ETL
    etl = SparkNYCTaxiETL(
        data_size=args.size, output_path=args.output, output_bucket=args.s3_bucket
    )

    start_time = datetime.now()
    results = etl.run()
    end_time = datetime.now()

    # Print summary
    print("\n" + "=" * 60)
    print("SPARK NYC TAXI ETL SUMMARY")
    print("=" * 60)
    print(f"Dataset: {results['dataset']}")
    print(f"Total Time: {results['total_time']:.2f}s")
    print(f"Records Processed: {results['records_processed']:,}")
    print(f"Output: {results['output_paths']['results_dir']}")
    print("\nTiming Breakdown:")
    print(f"  Startup: {results['metrics']['startup_time']:.2f}s")
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
