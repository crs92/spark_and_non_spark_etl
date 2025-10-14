"""non_spark_etl.py: Pythonic ETL implementation using Polars."""

import logging
import time
from pathlib import Path

import polars as pl

from src.etl.data_quality import (
    DataQualityConfig,
    DataQualityReport,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_non_spark_etl(
    input_path: str = "/app/data/input",
    output_path: str = "/app/data/output",
    quality_config: DataQualityConfig | None = None,
) -> tuple[Path, DataQualityReport]:
    """Run Pythonic ETL job using Polars with data quality checks.

    Args:
        input_path: Path to input data directory
        output_path: Path to output data directory
        quality_config: Data quality configuration (uses defaults if None)

    Returns:
        Tuple of (output_file_path, data_quality_report)
    """
    logger.info("Starting processing from %s to %s", input_path, output_path)

    if quality_config is None:
        quality_config = DataQualityConfig()

    # Simulate some processing time
    time.sleep(2)

    # Create sample data if input doesn't exist
    input_file = Path(input_path) / "sample_data.csv"
    if not input_file.exists():
        logger.info("Creating sample data...")
        from src.data_generation import generate_clickstream_data

        generate_clickstream_data(
            num_records=1000, output_path=str(input_file), format_type="csv"
        )

    # Read and process data
    logger.info("Reading data...")
    df = pl.read_csv(input_file)

    # Initialize quality tracking
    initial_count = len(df)
    null_counts = {}
    type_errors = {}
    validation_errors = {}
    records_dropped = 0
    records_corrected = 0

    # Data Quality Step 1: Track initial null counts
    logger.info("Performing data quality checks...")
    for col in df.columns:
        null_count = df[col].null_count()
        if null_count > 0:
            null_counts[col] = null_count
            logger.warning(f"Column '{col}' has {null_count} null values")

    # Data Quality Step 2: Type casting with error handling
    logger.info("Applying type casting...")

    # Cast timestamp to datetime with error handling
    try:
        df = df.with_columns([pl.col("timestamp").str.to_datetime().alias("timestamp")])
    except Exception as e:
        logger.error(f"Error casting timestamp: {e}")
        # Try to parse with more lenient format
        df = df.with_columns([
            pl.col("timestamp")
            .str.to_datetime("%Y-%m-%d %H:%M:%S%.f")
            .alias("timestamp")
        ])
        type_errors["timestamp"] = 1

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
    for col in string_columns:
        if col in df.columns:
            df = df.with_columns([pl.col(col).cast(pl.Utf8, strict=False).alias(col)])

    # Data Quality Step 3: Handle null values in required columns
    logger.info("Handling null values...")

    if quality_config.drop_null_event_id and "event_id" in df.columns:
        before = len(df)
        df = df.filter(pl.col("event_id").is_not_null())
        dropped = before - len(df)
        if dropped > 0:
            records_dropped += dropped
            logger.info(f"Dropped {dropped} records with null event_id")

    if quality_config.drop_null_user_id and "user_id" in df.columns:
        before = len(df)
        df = df.filter(pl.col("user_id").is_not_null())
        dropped = before - len(df)
        if dropped > 0:
            records_dropped += dropped
            logger.info(f"Dropped {dropped} records with null user_id")

    if quality_config.drop_null_timestamp and "timestamp" in df.columns:
        before = len(df)
        df = df.filter(pl.col("timestamp").is_not_null())
        dropped = before - len(df)
        if dropped > 0:
            records_dropped += dropped
            logger.info(f"Dropped {dropped} records with null timestamp")

    # Data Quality Step 4: Fill null values in optional columns
    if quality_config.fill_null_country and "country" in df.columns:
        before_nulls = df["country"].null_count()
        df = df.with_columns(
            [pl.col("country").fill_null(quality_config.default_country)]
        )
        if before_nulls > 0:
            records_corrected += before_nulls
            logger.info(
                f"Filled {before_nulls} null country values with"
                f" '{quality_config.default_country}'"
            )

    if quality_config.fill_null_device and "device" in df.columns:
        before_nulls = df["device"].null_count()
        df = df.with_columns(
            [pl.col("device").fill_null(quality_config.default_device)]
        )
        if before_nulls > 0:
            records_corrected += before_nulls
            logger.info(
                f"Filled {before_nulls} null device values with"
                f" '{quality_config.default_device}'"
            )

    # Data Quality Step 5: Remove duplicate event IDs
    if quality_config.drop_duplicate_event_ids and "event_id" in df.columns:
        before = len(df)
        df = df.unique(subset=["event_id"], keep="first")
        dropped = before - len(df)
        if dropped > 0:
            records_dropped += dropped
            validation_errors["duplicate_event_ids"] = dropped
            logger.info(f"Dropped {dropped} duplicate event_id records")

    # Data Quality Step 6: Validate IP address format
    if quality_config.validate_ip_format and "ip_address" in df.columns:
        # Mark invalid IPs (basic validation - should match IPv4 pattern)
        df = df.with_columns([
            pl.col("ip_address")
            .str.contains(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
            .alias("valid_ip")
        ])
        invalid_count = len(df.filter(~pl.col("valid_ip")))
        if invalid_count > 0:
            validation_errors["invalid_ip_format"] = invalid_count
            logger.warning(f"Found {invalid_count} records with invalid IP format")
            # Replace invalid IPs with a placeholder
            df = df.with_columns([
                pl.when(pl.col("valid_ip"))
                .then(pl.col("ip_address"))
                .otherwise(pl.lit("0.0.0.0"))
                .alias("ip_address")
            ])
            records_corrected += invalid_count
        df = df.drop("valid_ip")

    # Data Quality Step 7: Validate URL format
    if quality_config.validate_url_format and "page_url" in df.columns:
        # Ensure URLs start with /
        df = df.with_columns([
            pl.when(pl.col("page_url").str.starts_with("/"))
            .then(pl.col("page_url"))
            .otherwise(pl.lit("/") + pl.col("page_url"))
            .alias("page_url")
        ])

    # Implement proper sessionization with 30-minute inactivity window
    logger.info("Implementing sessionization logic...")

    # Sort by user_id and timestamp for sessionization
    df_sorted = df.sort(["user_id", "timestamp"])

    # Calculate time differences and session boundaries
    df_with_sessions = (
        df_sorted.with_columns([
            # Get previous timestamp for each user
            pl.col("timestamp")
            .shift(1)
            .over("user_id")
            .alias("prev_timestamp"),
        ])
        .with_columns([
            # Calculate time difference in minutes
            (
                (pl.col("timestamp") - pl.col("prev_timestamp")).dt.total_seconds() / 60
            ).alias("time_diff_minutes")
        ])
        .with_columns([
            # Mark session boundaries (new session if >30 minutes gap or first event)
            pl.when(
                (pl.col("time_diff_minutes") > 30) | pl.col("prev_timestamp").is_null()
            )
            .then(1)
            .otherwise(0)
            .alias("is_new_session")
        ])
        .with_columns([
            # Create session numbers by cumulative sum of session flags within each user
            pl.col("is_new_session")
            .cum_sum()
            .over("user_id")
            .alias("session_number")
        ])
        .with_columns([
            # Create session IDs
            (
                pl.col("user_id").cast(pl.Utf8)
                + "_"
                + pl.col("session_number").cast(pl.Utf8)
            ).alias("session_id")
        ])
    )

    # Calculate session duration and boundaries
    df_processed = (
        df_with_sessions.with_columns([
            # Session start and end times
            pl.col("timestamp").min().over("session_id").alias("session_start"),
            pl.col("timestamp").max().over("session_id").alias("session_end"),
        ])
        .with_columns([
            # Session duration in minutes
            (
                (pl.col("session_end") - pl.col("session_start")).dt.total_seconds()
                / 60
            ).alias("session_duration_minutes"),
            # IP suffix extraction
            pl.col("ip_address").str.extract(r"192\.168\.1\.(\d+)").alias("ip_suffix"),
            # Country (will be replaced with proper geolocation)
            pl.lit("US").alias("country"),
        ])
        .select([
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
        ])
    )

    # Write output
    output_file = Path(output_path) / "processed_data.parquet"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df_processed.write_parquet(output_file)

    # Create data quality report
    final_count = len(df_processed)
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

    return output_file, quality_report


if __name__ == "__main__":
    run_non_spark_etl()
