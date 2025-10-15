"""spark_etl.py: Spark ETL implementation using PySpark."""

import logging
import os
import time
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    coalesce,
    col,
    concat,
    lag,
    lit,
    regexp_extract,
    unix_timestamp,
    when,
)
from pyspark.sql.functions import sum as spark_sum
from pyspark.sql.types import StringType, TimestampType
from pyspark.sql.window import Window

from src.etl.data_quality import (
    DataQualityConfig,
    DataQualityReport,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_spark_etl(
    input_path: str = "/app/data/input",
    output_path: str = "/app/data/output",
    quality_config: DataQualityConfig | None = None,
) -> tuple[Path, DataQualityReport]:
    """Run Spark ETL job using PySpark with data quality checks.

    Args:
        input_path: Path to input data directory
        output_path: Path to output data directory
        quality_config: Data quality configuration (uses defaults if None)

    Returns:
        Tuple of (output_file_path, data_quality_report)
    """
    logger.info("Starting Spark processing from %s to %s", input_path, output_path)

    if quality_config is None:
        quality_config = DataQualityConfig()

    # Initialize Spark session with distributed configuration
    spark_builder = (
        SparkSession.builder.appName("DistributedSparkETL")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .config("spark.sql.adaptive.advisoryPartitionSizeInBytes", "128MB")
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

    # Log Spark configuration
    logger.info("Spark Master: %s", spark.sparkContext.master)
    logger.info("Spark App Name: %s", spark.sparkContext.appName)

    # Simulate some processing time
    time.sleep(3)  # Spark has more overhead

    # Create sample data if input doesn't exist
    input_file = Path(input_path) / "sample_data.csv"
    if not input_file.exists():
        logger.info("Creating sample data...")
        from src.data_generation.generator import generate_clickstream_data

        generate_clickstream_data(
            num_records=1000, output_path=str(input_file), format_type="csv"
        )

    # Read and process data
    logger.info("Reading data...")
    df = spark.read.option("header", "true").csv(str(input_file))

    # Initialize quality tracking
    initial_count = df.count()
    null_counts = {}
    type_errors = {}
    validation_errors = {}
    records_dropped = 0
    records_corrected = 0

    # Data Quality Step 1: Track initial null counts
    logger.info("Performing data quality checks...")
    for col_name in df.columns:
        null_count = df.filter(col(col_name).isNull()).count()
        if null_count > 0:
            null_counts[col_name] = null_count
            logger.warning(f"Column '{col_name}' has {null_count} null values")

    # Data Quality Step 2: Type casting with error handling
    logger.info("Applying type casting...")

    # Cast timestamp to proper timestamp type
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

    # Implement proper sessionization with 30-minute inactivity window
    logger.info("Implementing sessionization logic...")

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
    from pyspark.sql.functions import max as spark_max
    from pyspark.sql.functions import min as spark_min

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
        .withColumn(
            "ip_suffix", regexp_extract(col("ip_address"), r"192\.168\.1\.(\d+)", 1)
        )
        .withColumn("country", lit("US"))  # Will be replaced with proper geolocation
        .select(
            "event_id",
            "user_id",
            "session_id",
            "timestamp",
            "page_url",
            "country",
            "device",
            "ip_address",
            "ip_suffix",
            "session_start",
            "session_end",
            "session_duration_minutes",
        )
    )

    # Write output
    output_file = Path(output_path) / "processed_data.parquet"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df_processed.coalesce(1).write.mode("overwrite").parquet(
        str(output_file.parent / "spark_output"),
    )

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

    quality_report.log_summary()
    logger.info(
        "Completed. Processed %d records (from %d initial records)",
        final_count,
        initial_count,
    )

    spark.stop()
    return output_file, quality_report


if __name__ == "__main__":
    run_spark_etl()
