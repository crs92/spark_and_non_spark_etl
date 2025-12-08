#!/usr/bin/env python3
"""Spark ETL for NYC Taxi - Kubernetes/Spark Operator compatible version.

This version works with Spark Operator by NOT trying to configure Kubernetes.
The Spark Operator handles all K8s configuration.
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

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    avg,
    col,
    count,
    to_date,
)
from pyspark.sql.functions import sum as spark_sum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_spark_session():
    """Get or create Spark session - works with Spark Operator."""
    return SparkSession.builder.appName("SparkNYCTaxiETL").getOrCreate()


def main():
    parser = argparse.ArgumentParser(description="Spark ETL for NYC Taxi Dataset")
    parser.add_argument("--size", type=str, default="tiny", help="Dataset size")
    parser.add_argument("--output", type=str, default="/tmp/output", help="Output path")
    parser.add_argument("--s3-bucket", type=str, help="S3 bucket for output")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Spark NYC Taxi ETL - Kubernetes Mode")
    logger.info("=" * 60)
    logger.info("Dataset size: %s", args.size)
    logger.info("Output: %s", args.output)
    logger.info("S3 Bucket: %s", args.s3_bucket)
    logger.info("=" * 60)

    start_time = time.time()

    # Get Spark session (already configured by Spark Operator)
    spark = get_spark_session()
    logger.info("Spark Master: %s", spark.sparkContext.master)
    logger.info("Spark App ID: %s", spark.sparkContext.applicationId)

    # For tiny dataset, use a single file
    if args.size == "tiny":
        input_path = "s3a://ccorsetti/nyc-taxi/small/yellow_tripdata_2022-01.parquet"
    else:
        input_path = f"s3a://ccorsetti/nyc-taxi/{args.size}/*.parquet"

    logger.info("Reading from: %s", input_path)

    # EXTRACT
    logger.info("EXTRACT: Reading data...")
    extract_start = time.time()
    df = spark.read.parquet(input_path)
    initial_count = df.count()
    logger.info("Read %d records in %.2fs", initial_count, time.time() - extract_start)

    # TRANSFORM
    logger.info("TRANSFORM: Processing data...")
    transform_start = time.time()

    # Standardize column names
    if "tpep_pickup_datetime" in df.columns:
        df = df.withColumnRenamed("tpep_pickup_datetime", "pickup_datetime")
    if "PULocationID" in df.columns:
        df = df.withColumnRenamed("PULocationID", "pickup_location_id")

    # Filter invalid trips
    df = df.filter(
        (col("passenger_count") > 0)
        & (col("trip_distance") > 0)
        & (col("fare_amount") > 0)
        & (col("total_amount") > 0)
    )

    # Calculate price per mile
    df = df.withColumn("price_per_mile", col("total_amount") / col("trip_distance"))

    # Extract date components
    df = df.withColumn("date", to_date(col("pickup_datetime")))

    # Remove outliers
    df = df.filter(col("price_per_mile") < 100)

    # Aggregate
    result_df = df.groupBy("pickup_location_id", "date").agg(
        avg("fare_amount").alias("avg_fare"),
        avg("trip_distance").alias("avg_distance"),
        avg("price_per_mile").alias("avg_price_per_mile"),
        spark_sum("passenger_count").alias("total_passengers"),
        count("*").alias("trip_count"),
    )

    result_df = result_df.orderBy(col("trip_count").desc())
    final_count = result_df.count()
    logger.info(
        "Transformed to %d aggregated records in %.2fs",
        final_count,
        time.time() - transform_start,
    )

    # LOAD
    logger.info("LOAD: Writing results...")
    load_start = time.time()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Write to S3 if bucket specified
    if args.s3_bucket:
        s3_path = f"{args.s3_bucket}/spark/{args.size}/results_{timestamp}"
        s3a_path = s3_path.replace("s3://", "s3a://")
        logger.info("Writing to S3: %s", s3_path)
        result_df.coalesce(1).write.mode("overwrite").parquet(s3a_path)
        logger.info("Results written to S3 in %.2fs", time.time() - load_start)

    # Also write locally
    local_path = f"{args.output}/results_{timestamp}"
    Path(local_path).mkdir(parents=True, exist_ok=True)
    result_df.coalesce(1).write.mode("overwrite").parquet(local_path)

    total_time = time.time() - start_time

    # Write metadata
    metadata = {
        "framework": "spark",
        "dataset": args.size,
        "execution_time": total_time,
        "initial_records": initial_count,
        "final_records": final_count,
        "timestamp": timestamp,
        "spark_app_id": spark.sparkContext.applicationId,
    }

    metadata_file = f"{args.output}/metadata_{timestamp}.json"
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info("=" * 60)
    logger.info("COMPLETED in %.2fs", total_time)
    logger.info("Initial records: %d", initial_count)
    logger.info("Final records: %d", final_count)
    logger.info("=" * 60)

    spark.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
