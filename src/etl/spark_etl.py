"""spark_etl.py: Spark ETL implementation using PySpark.

This ETL pipeline supports two modes:
- Bulk mode: Process large historical datasets (30 days)
- Incremental mode: Process daily incremental files and merge with existing data

Features:
- Proper sessionization with 30-minute inactivity window
- Data quality checks and cleansing
- Performance metrics tracking
- Support for CSV and Parquet formats
"""

import argparse
import logging
import os
import time
from datetime import datetime
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    coalesce,
    col,
    concat,
    lag,
    lit,
    unix_timestamp,
    when,
)
from pyspark.sql.functions import max as spark_max
from pyspark.sql.functions import min as spark_min
from pyspark.sql.functions import sum as spark_sum
from pyspark.sql.types import StringType, TimestampType
from pyspark.sql.window import Window

from src.etl.data_quality import (
    DataQualityConfig,
    DataQualityReport,
)
from src.etl.iceberg_config import IcebergConfig
from src.etl.timing_decorator import PipelineTimer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_spark_etl(
    input_path: str = "data/generated/bulk/bulk_data_small.parquet",
    output_path: str = "data/output/spark",
    mode: str = "bulk",
    quality_config: DataQualityConfig | None = None,
    bulk_data_path: str | None = None,
    use_iceberg: bool = True,
    iceberg_config: IcebergConfig | None = None,
) -> dict:
    """Run Spark ETL job using PySpark with data quality checks.

    Args:
        input_path: Path to input data (file for bulk, directory for incremental)
        output_path: Path to output data directory
        mode: Processing mode ('bulk' or 'incremental')
        quality_config: Data quality configuration (uses defaults if None)
        bulk_data_path: Path to bulk data for incremental merge (optional, not used with Iceberg)
        use_iceberg: Whether to use Iceberg tables for output
        iceberg_config: Iceberg configuration

    Returns:
        Dictionary with metrics and results
    """
    if iceberg_config is None:
        iceberg_config = IcebergConfig()

    table_name = "etl.clickstream_events"

    logger.info("=" * 60)
    logger.info("Running Spark ETL Pipeline - %s mode", mode.upper())
    logger.info("=" * 60)
    logger.info("Input: %s", input_path)
    if use_iceberg:
        logger.info("Output: Iceberg table %s", table_name)
    else:
        logger.info("Output: %s", output_path)

    # Initialize timing
    timer = PipelineTimer(framework="spark", mode=mode)
    timer.start_pipeline()

    total_start = time.time()
    metrics = {
        "read_time": 0.0,
        "quality_check_time": 0.0,
        "sessionization_time": 0.0,
        "merge_time": 0.0,
        "write_time": 0.0,
        "total_time": 0.0,
    }

    if quality_config is None:
        quality_config = DataQualityConfig()

    # Initialize Spark session with distributed configuration
    spark_init_start = time.time()
    spark_builder = (
        SparkSession.builder.appName("SparkETL")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .config("spark.sql.adaptive.advisoryPartitionSizeInBytes", "128MB")
    )

    # Add Iceberg configuration if needed
    if use_iceberg:
        warehouse_path = iceberg_config.warehouse_path.absolute()

        # Find Iceberg Spark runtime JAR matching PySpark version
        import pyspark

        spark_version = pyspark.__version__
        spark_major = spark_version.split(".")[0]

        # Try to find matching JAR
        ivy2_cache = Path.home() / ".ivy2" / "cache" / "org.apache.iceberg"
        ivy2_jars = Path.home() / ".ivy2" / "jars"

        iceberg_jar = None

        # First try cache directory for Spark 4.0
        if spark_major == "4":
            cache_jars = list(
                ivy2_cache.glob(f"iceberg-spark-runtime-{spark_major}.0_*/jars/*.jar")
            )
            if cache_jars:
                iceberg_jar = str(cache_jars[0])

        # Fallback to jars directory
        if not iceberg_jar:
            jar_files = list(
                ivy2_jars.glob(
                    f"org.apache.iceberg_iceberg-spark-runtime-{spark_major}*.jar"
                )
            )
            if jar_files:
                iceberg_jar = str(jar_files[0])

        if iceberg_jar:
            logger.info("Using Iceberg JAR: %s", iceberg_jar)
            spark_builder = spark_builder.config("spark.jars", iceberg_jar)
        else:
            logger.warning(
                "No Iceberg Spark runtime JAR found for Spark %s. Download with:"
                " spark-shell --packages"
                " org.apache.iceberg:iceberg-spark-runtime-%s.0_2.13:1.6.1",
                spark_version,
                spark_major,
            )

        spark_builder = (
            spark_builder.config(
                "spark.sql.extensions",
                "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
            )
            .config("spark.sql.catalog.local", "org.apache.iceberg.spark.SparkCatalog")
            .config("spark.sql.catalog.local.type", "hadoop")
            .config("spark.sql.catalog.local.warehouse", f"file://{warehouse_path}")
        )

    # Check if running in Kubernetes (distributed mode)
    if os.getenv("SPARK_MASTER_URL", "").startswith("k8s://"):
        logger.info("Configuring Spark for Kubernetes distributed processing")
        spark_builder = (
            spark_builder.config("spark.master", os.getenv("SPARK_MASTER_URL"))
            .config(
                "spark.executor.instances",
                os.getenv("SPARK_EXECUTOR_INSTANCES", "2"),
            )
            .config(
                "spark.executor.memory",
                os.getenv("SPARK_EXECUTOR_MEMORY", "2g"),
            )
            .config(
                "spark.executor.cores",
                os.getenv("SPARK_EXECUTOR_CORES", "2"),
            )
            .config("spark.kubernetes.container.image", "spark-etl:latest")
            .config("spark.kubernetes.namespace", "default")
            .config("spark.kubernetes.executor.request.cores", "1")
            .config("spark.kubernetes.executor.limit.cores", "2")
        )
    else:
        logger.info("Configuring Spark for local processing")
        spark_builder = spark_builder.master("local[*]")

    spark = spark_builder.getOrCreate()

    # Track Spark initialization time
    timer.metrics["startup_time"] = time.time() - spark_init_start

    # Log Spark configuration
    logger.info("Spark Master: %s", spark.sparkContext.master)
    logger.info("Spark App Name: %s", spark.sparkContext.appName)
    logger.info("Spark initialization took %.2fs", timer.metrics["startup_time"])

    # Read data based on mode
    logger.info("Reading data in %s mode...", mode)
    read_start = time.time()

    input_path_obj = Path(input_path)

    if mode == "bulk":
        # Read bulk data file
        if input_path_obj.suffix == ".csv":
            df = spark.read.option("header", "true").csv(str(input_path_obj))
        elif input_path_obj.suffix == ".parquet":
            df = spark.read.parquet(str(input_path_obj))
        else:
            raise ValueError(f"Unsupported file format: {input_path_obj.suffix}")
    else:
        # Read incremental files from directory
        if not input_path_obj.is_dir():
            raise ValueError(
                f"Incremental mode requires directory path, got: {input_path_obj}"
            )

        # Find all incremental files
        csv_files = list(input_path_obj.glob("incremental_*.csv"))
        parquet_files = list(input_path_obj.glob("incremental_*.parquet"))

        if parquet_files:
            df = spark.read.parquet(str(input_path_obj / "incremental_*.parquet"))
        elif csv_files:
            df = spark.read.option("header", "true").csv(
                str(input_path_obj / "incremental_*.csv")
            )
        else:
            raise ValueError(f"No incremental files found in {input_path_obj}")

    metrics["read_time"] = time.time() - read_start
    timer.metrics["extract"]["total"] = metrics["read_time"]

    logger.info(
        "Read completed in %.2fs - %d records loaded", metrics["read_time"], df.count()
    )

    timer.sample_memory()

    # Initialize quality tracking
    logger.info("Applying data quality checks...")
    quality_start = time.time()

    initial_count = df.count()
    null_counts = {}
    type_errors = {}
    validation_errors = {}
    records_dropped = 0
    records_corrected = 0

    # Data Quality Step 1: Track initial null counts
    for col_name in df.columns:
        null_count = df.filter(col(col_name).isNull()).count()
        if null_count > 0:
            null_counts[col_name] = null_count
            logger.warning(f"Column '{col_name}' has {null_count} null values")

    # Data Quality Step 2: Type casting with error handling
    # Cast timestamp to proper timestamp type (if it's a string)
    if dict(df.dtypes)["timestamp"] == "string":
        df = df.withColumn("timestamp", col("timestamp").cast(TimestampType()))

    # Ensure string types for text columns
    string_columns = [
        "event_id",
        "user_id",
        "session_id",
        "page_url",
        "country",
        "device",
        "ip_address",
    ]
    for col_name in string_columns:
        if col_name in df.columns:
            df = df.withColumn(col_name, col(col_name).cast(StringType()))

    # Data Quality Step 3: Handle null values in required columns
    logger.info("Handling null values...")

    if quality_config.drop_null_event_id:
        before = df.count()
        df = df.filter(col("event_id").isNotNull())
        dropped = before - df.count()
        if dropped > 0:
            records_dropped += dropped
            logger.info(f"Dropped {dropped} records with null event_id")

    if quality_config.drop_null_user_id:
        before = df.count()
        df = df.filter(col("user_id").isNotNull())
        dropped = before - df.count()
        if dropped > 0:
            records_dropped += dropped
            logger.info(f"Dropped {dropped} records with null user_id")

    if quality_config.drop_null_timestamp:
        before = df.count()
        df = df.filter(col("timestamp").isNotNull())
        dropped = before - df.count()
        if dropped > 0:
            records_dropped += dropped
            logger.info(f"Dropped {dropped} records with null timestamp")

    # Data Quality Step 4: Fill null values in optional columns
    if quality_config.fill_null_country:
        before_nulls = df.filter(col("country").isNull()).count()
        df = df.withColumn(
            "country", coalesce(col("country"), lit(quality_config.default_country))
        )
        if before_nulls > 0:
            records_corrected += before_nulls
            logger.info(
                f"Filled {before_nulls} null country values with"
                f" '{quality_config.default_country}'"
            )

    if quality_config.fill_null_device:
        before_nulls = df.filter(col("device").isNull()).count()
        df = df.withColumn(
            "device", coalesce(col("device"), lit(quality_config.default_device))
        )
        if before_nulls > 0:
            records_corrected += before_nulls
            logger.info(
                f"Filled {before_nulls} null device values with"
                f" '{quality_config.default_device}'"
            )

    # Data Quality Step 5: Remove duplicate event IDs
    if quality_config.drop_duplicate_event_ids:
        before = df.count()
        df = df.dropDuplicates(["event_id"])
        dropped = before - df.count()
        if dropped > 0:
            records_dropped += dropped
            validation_errors["duplicate_event_ids"] = dropped
            logger.info(f"Dropped {dropped} duplicate event_id records")

    # Data Quality Step 6: Validate IP address format
    if quality_config.validate_ip_format:
        # Mark invalid IPs (basic validation - should match IPv4 pattern)
        df = df.withColumn(
            "valid_ip", col("ip_address").rlike(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
        )
        invalid_count = df.filter(~col("valid_ip")).count()
        if invalid_count > 0:
            validation_errors["invalid_ip_format"] = invalid_count
            logger.warning(f"Found {invalid_count} records with invalid IP format")
            # Replace invalid IPs with a placeholder
            df = df.withColumn(
                "ip_address",
                when(col("valid_ip"), col("ip_address")).otherwise(lit("0.0.0.0")),
            )
            records_corrected += invalid_count
        df = df.drop("valid_ip")

    # Data Quality Step 7: Validate URL format
    if quality_config.validate_url_format:
        # Ensure URLs start with /
        df = df.withColumn(
            "page_url",
            when(col("page_url").startswith("/"), col("page_url")).otherwise(
                concat(lit("/"), col("page_url"))
            ),
        )

    metrics["quality_check_time"] = time.time() - quality_start
    timer.metrics["transform"]["quality_checks"] = metrics["quality_check_time"]

    logger.info("Quality checks completed in %.2fs", metrics["quality_check_time"])

    timer.sample_memory()

    # Implement proper sessionization with 30-minute inactivity window
    logger.info("Applying sessionization logic...")
    sessionization_start = time.time()

    # Define window for sessionization - partition by user_id and order by timestamp
    user_window = Window.partitionBy("user_id").orderBy("timestamp")

    # Calculate time difference between consecutive events for each user
    df_with_time_diff = df.withColumn(
        "prev_timestamp", lag("timestamp").over(user_window)
    ).withColumn(
        "time_diff_minutes",
        (unix_timestamp("timestamp") - unix_timestamp("prev_timestamp")) / 60,
    )

    # Mark session boundaries (new session if >30 minutes gap or first event)
    df_with_session_flags = df_with_time_diff.withColumn(
        "is_new_session",
        when(
            (col("time_diff_minutes") > 30) | col("prev_timestamp").isNull(), 1
        ).otherwise(0),
    )

    # Create session IDs by cumulative sum of session flags
    df_with_sessions = (
        df_with_session_flags.withColumn(
            "session_number", spark_sum("is_new_session").over(user_window)
        )
        .withColumn(
            "new_session_id",
            concat(col("user_id"), lit("_"), col("session_number").cast("string")),
        )
        .drop("session_id")
        .withColumnRenamed("new_session_id", "session_id")
    )

    # Calculate session duration and boundaries using proper window functions
    session_agg_window = Window.partitionBy("session_id")

    df_processed = (
        df_with_sessions.withColumn(
            "session_start", spark_min("timestamp").over(session_agg_window)
        )
        .withColumn("session_end", spark_max("timestamp").over(session_agg_window))
        .withColumn(
            "session_duration_minutes",
            (unix_timestamp("session_end") - unix_timestamp("session_start")) / 60,
        )
        .select(
            "event_id",
            "user_id",
            "session_id",
            "timestamp",
            "page_url",
            "country",
            "device",
            "ip_address",
            "session_start",
            "session_end",
            "session_duration_minutes",
        )
    )

    metrics["sessionization_time"] = time.time() - sessionization_start
    timer.metrics["transform"]["sessionization"] = metrics["sessionization_time"]
    timer.metrics["transform"]["total"] = (
        timer.metrics["transform"]["quality_checks"]
        + timer.metrics["transform"]["sessionization"]
    )

    logger.info("Sessionization completed in %.2fs", metrics["sessionization_time"])

    timer.sample_memory()

    # For incremental mode, merge with bulk data if provided
    if mode == "incremental" and bulk_data_path:
        logger.info("Merging incremental data with bulk data from %s", bulk_data_path)
        merge_start = time.time()

        bulk_path_obj = Path(bulk_data_path)
        if bulk_path_obj.suffix == ".parquet":
            bulk_df = spark.read.parquet(str(bulk_path_obj))
        elif bulk_path_obj.suffix == ".csv":
            bulk_df = spark.read.option("header", "true").csv(str(bulk_path_obj))
        else:
            raise ValueError(f"Unsupported bulk file format: {bulk_path_obj.suffix}")

        logger.info("Loaded %d records from bulk data", bulk_df.count())

        # Select only base columns for merging
        base_columns = [
            "event_id",
            "user_id",
            "timestamp",
            "page_url",
            "country",
            "device",
            "ip_address",
        ]

        bulk_df = bulk_df.select(*base_columns)
        df_processed = df_processed.select(*base_columns)

        # Union bulk and incremental data
        combined_df = bulk_df.union(df_processed)
        logger.info("Combined data: %d records", combined_df.count())

        # Remove duplicates based on event_id (keep latest)
        combined_df = combined_df.dropDuplicates(["event_id"])
        logger.info("After deduplication: %d records", combined_df.count())

        # Re-apply sessionization to the merged data
        logger.info("Re-applying sessionization to merged data...")
        user_window = Window.partitionBy("user_id").orderBy("timestamp")

        combined_df = combined_df.withColumn(
            "prev_timestamp", lag("timestamp").over(user_window)
        ).withColumn(
            "time_diff_minutes",
            (unix_timestamp("timestamp") - unix_timestamp("prev_timestamp")) / 60,
        )

        combined_df = combined_df.withColumn(
            "is_new_session",
            when(
                (col("time_diff_minutes") > 30) | col("prev_timestamp").isNull(), 1
            ).otherwise(0),
        )

        combined_df = combined_df.withColumn(
            "session_number", spark_sum("is_new_session").over(user_window)
        ).withColumn(
            "session_id",
            concat(col("user_id"), lit("_"), col("session_number").cast("string")),
        )

        session_agg_window = Window.partitionBy("session_id")

        df_processed = (
            combined_df.withColumn(
                "session_start", spark_min("timestamp").over(session_agg_window)
            )
            .withColumn("session_end", spark_max("timestamp").over(session_agg_window))
            .withColumn(
                "session_duration_minutes",
                (unix_timestamp("session_end") - unix_timestamp("session_start")) / 60,
            )
            .select(
                "event_id",
                "user_id",
                "session_id",
                "timestamp",
                "page_url",
                "country",
                "device",
                "ip_address",
                "session_start",
                "session_end",
                "session_duration_minutes",
            )
        )

        metrics["merge_time"] = time.time() - merge_start
        logger.info("Merge completed in %.2fs", metrics["merge_time"])

    # Write output
    write_start = time.time()

    if use_iceberg:
        # Write to Iceberg table
        logger.info("Writing to Iceberg table: %s (mode: %s)", table_name, mode)

        # Create namespace if it doesn't exist
        spark.sql("CREATE NAMESPACE IF NOT EXISTS local.etl")

        if mode == "bulk":
            # Bulk mode: Create or replace table
            logger.info("Performing bulk write (create or replace)")
            df_processed.writeTo(f"local.{table_name}").createOrReplace()
            logger.info(
                "Bulk write completed - %d records written", df_processed.count()
            )
            output_location = table_name

        else:  # incremental mode
            # Incremental mode: Merge/upsert based on event_id
            logger.info("Performing incremental merge (upsert on event_id)")

            # Check if table exists
            table_exists = spark.catalog.tableExists(f"local.{table_name}")

            if not table_exists:
                # Table doesn't exist, create it
                logger.info("Table doesn't exist, creating with initial data")
                df_processed.writeTo(f"local.{table_name}").create()
                logger.info("Created table with %d records", df_processed.count())
            else:
                # Table exists, perform merge
                # Create temp view for new data
                df_processed.createOrReplaceTempView("new_data")

                # Perform merge using SQL
                merge_sql = f"""
                MERGE INTO local.{table_name} AS target
                USING new_data AS source
                ON target.event_id = source.event_id
                WHEN MATCHED THEN UPDATE SET *
                WHEN NOT MATCHED THEN INSERT *
                """

                spark.sql(merge_sql)

                # Get final count
                final_count = spark.sql(
                    f"SELECT COUNT(*) as cnt FROM local.{table_name}"
                ).collect()[0]["cnt"]
                logger.info(
                    "Incremental merge completed - %d new records, %d total records",
                    df_processed.count(),
                    final_count,
                )

            output_location = table_name
    else:
        # Write to file
        logger.info("Writing output to %s", output_path)
        output_file = Path(output_path) / f"spark_output_{mode}.parquet"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        df_processed.coalesce(1).write.mode("overwrite").parquet(str(output_file))
        output_location = str(output_file)

    metrics["write_time"] = time.time() - write_start
    timer.metrics["load"]["write"] = metrics["write_time"]
    timer.metrics["load"]["total"] = metrics["write_time"]

    logger.info("Write completed in %.2fs", metrics["write_time"])

    timer.sample_memory()

    # Create data quality report
    final_count = df_processed.count()
    records_with_issues = records_dropped + records_corrected

    quality_report = DataQualityReport(
        total_records=initial_count,
        records_with_issues=records_with_issues,
        records_dropped=records_dropped,
        records_corrected=records_corrected,
        null_counts=null_counts,
        type_errors=type_errors,
        validation_errors=validation_errors,
    )

    metrics["total_time"] = time.time() - total_start

    # End pipeline timing
    timer.end_pipeline()

    logger.info("=" * 60)
    logger.info("Pipeline completed in %.2fs", metrics["total_time"])
    logger.info("=" * 60)

    quality_report.log_summary()
    logger.info(
        "Processed %d records (from %d initial records)",
        final_count,
        initial_count,
    )

    # Log timing summary
    timer.log_summary()

    spark.stop()

    return {
        "mode": mode,
        "total_time": metrics["total_time"],
        "metrics": metrics,
        "timing_metrics": timer.metrics,
        "records_processed": final_count,
        "output_location": output_location,
        "use_iceberg": use_iceberg,
        "quality_report": quality_report,
    }


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Spark ETL Pipeline - Bulk and Incremental Processing"
    )
    parser.add_argument(
        "--mode",
        choices=["bulk", "incremental"],
        default="bulk",
        help="Processing mode (default: bulk)",
    )
    parser.add_argument(
        "--input",
        default="data/generated/bulk/bulk_data_small.parquet",
        help="Input path (file for bulk, directory for incremental)",
    )
    parser.add_argument(
        "--output",
        default="data/output/spark",
        help="Output directory (default: data/output/spark)",
    )
    parser.add_argument(
        "--bulk-data",
        help=(
            "Path to bulk data for incremental merge (optional, not used with Iceberg)"
        ),
    )
    parser.add_argument(
        "--no-iceberg",
        action="store_true",
        help="Disable Iceberg table output (use Parquet files instead)",
    )

    args = parser.parse_args()

    # Adjust input path for incremental mode
    if (
        args.mode == "incremental"
        and args.input == "data/generated/bulk/bulk_data_small.parquet"
    ):
        args.input = "data/generated/incremental"

    # Set default bulk data path for incremental mode (only if not using Iceberg)
    if args.mode == "incremental" and not args.bulk_data and args.no_iceberg:
        args.bulk_data = "data/output/spark/spark_output_bulk.parquet"

    use_iceberg = not args.no_iceberg

    logger.info("Starting Spark ETL Pipeline")
    logger.info("Mode: %s", args.mode)
    logger.info("Input: %s", args.input)
    logger.info("Output: %s", args.output)
    logger.info("Use Iceberg: %s", use_iceberg)
    if args.bulk_data:
        logger.info("Bulk data: %s", args.bulk_data)

    start_time = datetime.now()
    results = run_spark_etl(
        input_path=args.input,
        output_path=args.output,
        mode=args.mode,
        bulk_data_path=args.bulk_data,
        use_iceberg=use_iceberg,
    )
    end_time = datetime.now()

    # Print summary
    print("\n" + "=" * 60)
    print("SPARK ETL SUMMARY")
    print("=" * 60)
    print(f"Mode: {results['mode']}")
    print(f"Total Time: {results['total_time']:.2f}s")
    print(f"Records Processed: {results['records_processed']:,}")
    print(f"Output Location: {results['output_location']}")
    if results.get("use_iceberg"):
        print("Output Type: Iceberg Table")
    else:
        print("Output Type: File")
    print("\nMetrics Breakdown:")
    for metric, duration in results["metrics"].items():
        print(f"  {metric}: {duration:.2f}s")
    print("=" * 60)
    print(f"Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Ended: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
