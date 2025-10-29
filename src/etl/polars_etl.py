"""Polars ETL - Bulk and Incremental Pipeline Implementation

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
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl
import pyarrow as pa
from pyiceberg.schema import Schema
from pyiceberg.types import (
    DoubleType,
    NestedField,
    StringType,
    TimestampType,
)

from src.etl.data_quality import DataQualityConfig, DataQualityReport
from src.etl.iceberg_config import IcebergConfig
from src.etl.timing_decorator import PipelineTimer, timed_phase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PolarsPipeline:
    """Bulk and Incremental ETL pipeline using Polars."""

    def __init__(
        self,
        input_path: str,
        output_path: str,
        mode: str = "bulk",
        quality_config: DataQualityConfig | None = None,
        use_iceberg: bool = True,
        iceberg_config: IcebergConfig | None = None,
    ):
        """Initialize pipeline with input/output paths.

        Args:
            input_path (str): Path to input data (file or directory)
            output_path (str): Path to output directory
            mode (str): Processing mode ('bulk' or 'incremental')
            quality_config (DataQualityConfig | None): Data quality configuration
            use_iceberg (bool): Whether to use Iceberg tables for output
            iceberg_config (IcebergConfig | None): Iceberg configuration
        """
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.output_path.mkdir(parents=True, exist_ok=True)
        self.mode = mode
        self.quality_config = quality_config or DataQualityConfig()
        self.use_iceberg = use_iceberg
        self.iceberg_config = iceberg_config or IcebergConfig()

        self.df = None
        self.catalog = None
        self.table_name = "etl.clickstream_events"
        self.metrics = {
            "read_time": 0.0,
            "quality_check_time": 0.0,
            "sessionization_time": 0.0,
            "merge_time": 0.0,
            "write_time": 0.0,
            "total_time": 0.0,
        }
        self.quality_report = None

        # Simple timing decorator
        self._timer = PipelineTimer(framework="polars", mode=mode)

        # Initialize Iceberg catalog if needed
        if self.use_iceberg:
            self._init_iceberg_catalog()

    def _init_iceberg_catalog(self):
        """Initialize Iceberg catalog and create table if needed."""
        try:
            self.catalog = self.iceberg_config.get_catalog()
            logger.info("Iceberg catalog initialized")

            # Create namespace if it doesn't exist
            namespace = self.table_name.split(".")[0]
            try:
                self.catalog.create_namespace(namespace)
                logger.info("Created Iceberg namespace: %s", namespace)
            except Exception:
                logger.debug("Namespace %s already exists", namespace)

        except Exception as e:
            logger.error("Failed to initialize Iceberg catalog: %s", e)
            raise

    def _create_iceberg_table_if_not_exists(self):
        """Create Iceberg table with schema if it doesn't exist."""
        try:
            # Check if table exists
            self.catalog.load_table(self.table_name)
            logger.info("Iceberg table %s already exists", self.table_name)
        except Exception:
            # Table doesn't exist, create it
            logger.info("Creating Iceberg table: %s", self.table_name)

            # Define schema
            schema = Schema(
                NestedField(1, "event_id", StringType(), required=True),
                NestedField(2, "user_id", StringType(), required=True),
                NestedField(3, "session_id", StringType(), required=False),
                NestedField(4, "timestamp", TimestampType(), required=True),
                NestedField(5, "page_url", StringType(), required=False),
                NestedField(6, "country", StringType(), required=False),
                NestedField(7, "device", StringType(), required=False),
                NestedField(8, "ip_address", StringType(), required=False),
                NestedField(9, "session_start", TimestampType(), required=False),
                NestedField(10, "session_end", TimestampType(), required=False),
                NestedField(
                    11, "session_duration_minutes", DoubleType(), required=False
                ),
            )

            # Create table with event_id as primary key
            self.catalog.create_table(
                identifier=self.table_name,
                schema=schema,
            )
            logger.info("Created Iceberg table: %s", self.table_name)

    @timed_phase("extract")
    def read_data(self) -> pl.DataFrame:
        """Read data based on mode (bulk or incremental).

        Returns:
            DataFrame with raw data
        """
        logger.info("Reading data in %s mode from %s", self.mode, self.input_path)
        start = time.time()

        if self.mode == "bulk":
            # Read bulk data file
            if self.input_path.suffix == ".csv":
                self.df = pl.read_csv(self.input_path)
            elif self.input_path.suffix == ".parquet":
                self.df = pl.read_parquet(self.input_path)
            else:
                raise ValueError(f"Unsupported file format: {self.input_path.suffix}")
        else:
            # Read incremental files from directory
            if not self.input_path.is_dir():
                raise ValueError(
                    f"Incremental mode requires directory path, got: {self.input_path}"
                )

            # Find all incremental files
            csv_files = sorted(self.input_path.glob("incremental_*.csv"))
            parquet_files = sorted(self.input_path.glob("incremental_*.parquet"))

            if csv_files:
                self.df = pl.concat([pl.read_csv(f) for f in csv_files])
            elif parquet_files:
                self.df = pl.concat([pl.read_parquet(f) for f in parquet_files])
            else:
                raise ValueError(f"No incremental files found in {self.input_path}")

        self.metrics["read_time"] = time.time() - start
        logger.info(
            "Read completed in %.2fs - %d records loaded",
            self.metrics["read_time"],
            len(self.df),
        )

        return self.df

    @timed_phase("transform", "quality_checks")
    def apply_data_quality(self) -> pl.DataFrame:
        """Apply data quality checks and cleansing.

        Returns:
            Cleaned DataFrame with quality report
        """
        logger.info("Applying data quality checks...")
        start = time.time()

        initial_count = len(self.df)
        null_counts = {}
        records_dropped = 0
        records_corrected = 0
        validation_errors = {}

        # Track null counts
        for col_name in self.df.columns:
            null_count = self.df.filter(pl.col(col_name).is_null()).height
            if null_count > 0:
                null_counts[col_name] = null_count

        # Type casting - handle both string and datetime timestamps
        timestamp_col = self.df["timestamp"]
        if timestamp_col.dtype == pl.Utf8:
            self.df = self.df.with_columns([pl.col("timestamp").str.to_datetime()])

        # Cast other columns to string
        string_columns = [
            "event_id",
            "user_id",
            "page_url",
            "country",
            "device",
            "ip_address",
        ]
        for col_name in string_columns:
            if col_name in self.df.columns:
                self.df = self.df.with_columns([pl.col(col_name).cast(pl.Utf8)])

        # Drop null values in required columns
        if self.quality_config.drop_null_event_id:
            before = len(self.df)
            self.df = self.df.filter(pl.col("event_id").is_not_null())
            records_dropped += before - len(self.df)

        if self.quality_config.drop_null_user_id:
            before = len(self.df)
            self.df = self.df.filter(pl.col("user_id").is_not_null())
            records_dropped += before - len(self.df)

        if self.quality_config.drop_null_timestamp:
            before = len(self.df)
            self.df = self.df.filter(pl.col("timestamp").is_not_null())
            records_dropped += before - len(self.df)

        # Fill null values in optional columns
        if self.quality_config.fill_null_country:
            before_nulls = self.df.filter(pl.col("country").is_null()).height
            self.df = self.df.with_columns(
                pl.col("country").fill_null(self.quality_config.default_country)
            )
            records_corrected += before_nulls

        if self.quality_config.fill_null_device:
            before_nulls = self.df.filter(pl.col("device").is_null()).height
            self.df = self.df.with_columns(
                pl.col("device").fill_null(self.quality_config.default_device)
            )
            records_corrected += before_nulls

        # Remove duplicate event IDs
        if self.quality_config.drop_duplicate_event_ids:
            before = len(self.df)
            self.df = self.df.unique(subset=["event_id"])
            dropped = before - len(self.df)
            records_dropped += dropped
            if dropped > 0:
                validation_errors["duplicate_event_ids"] = dropped

        # Validate IP format
        if self.quality_config.validate_ip_format:
            invalid_mask = ~self.df["ip_address"].str.contains(
                r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"
            )
            invalid_count = invalid_mask.sum()
            if invalid_count > 0:
                validation_errors["invalid_ip_format"] = invalid_count
                self.df = self.df.with_columns(
                    pl.when(invalid_mask)
                    .then(pl.lit("0.0.0.0"))
                    .otherwise(pl.col("ip_address"))
                    .alias("ip_address")
                )
                records_corrected += invalid_count

        # Create quality report
        self.quality_report = DataQualityReport(
            total_records=initial_count,
            records_with_issues=records_dropped + records_corrected,
            records_dropped=records_dropped,
            records_corrected=records_corrected,
            null_counts=null_counts,
            type_errors={},
            validation_errors=validation_errors,
        )

        self.metrics["quality_check_time"] = time.time() - start
        logger.info(
            "Quality checks completed in %.2fs - %d records after cleaning",
            self.metrics["quality_check_time"],
            len(self.df),
        )

        return self.df

    @timed_phase("transform", "sessionization")
    def apply_sessionization(self) -> pl.DataFrame:
        """Apply proper sessionization with 30-minute inactivity window.

        Returns:
            DataFrame with session information
        """
        logger.info("Applying sessionization logic...")
        start = time.time()

        # Sort by user_id and timestamp
        self.df = self.df.sort(["user_id", "timestamp"])

        # Calculate time difference between consecutive events for each user
        self.df = self.df.with_columns([
            pl.col("timestamp").shift(1).over("user_id").alias("prev_timestamp"),
        ])

        # Calculate time difference in minutes
        self.df = self.df.with_columns([
            (
                (pl.col("timestamp") - pl.col("prev_timestamp")).dt.total_seconds() / 60
            ).alias("time_diff_minutes")
        ])

        # Mark session boundaries (new session if >30 minutes gap or first event)
        self.df = self.df.with_columns([
            pl.when(
                (pl.col("time_diff_minutes") > 30) | pl.col("prev_timestamp").is_null()
            )
            .then(1)
            .otherwise(0)
            .alias("is_new_session")
        ])

        # Create session IDs by cumulative sum of session flags
        self.df = self.df.with_columns(
            [pl.col("is_new_session").cum_sum().over("user_id").alias("session_number")]
        )

        # Drop old session_id and create new one
        if "session_id" in self.df.columns:
            self.df = self.df.drop("session_id")

        self.df = self.df.with_columns([
            (pl.col("user_id") + "_" + pl.col("session_number").cast(pl.Utf8)).alias(
                "session_id"
            )
        ])

        # Calculate session start, end, and duration
        self.df = self.df.with_columns([
            pl.col("timestamp").min().over("session_id").alias("session_start"),
            pl.col("timestamp").max().over("session_id").alias("session_end"),
        ])

        self.df = self.df.with_columns([
            (
                (pl.col("session_end") - pl.col("session_start")).dt.total_seconds()
                / 60
            ).alias("session_duration_minutes")
        ])

        # Clean up temporary columns
        self.df = self.df.drop(
            ["prev_timestamp", "time_diff_minutes", "is_new_session", "session_number"]
        )

        self.metrics["sessionization_time"] = time.time() - start
        logger.info(
            "Sessionization completed in %.2fs",
            self.metrics["sessionization_time"],
        )

        return self.df

    def merge_with_bulk(self, bulk_path: Path) -> pl.DataFrame:
        """Merge incremental data with existing bulk data.

        Args:
            bulk_path: Path to bulk data file

        Returns:
            Merged DataFrame
        """
        logger.info("Merging incremental data with bulk data from %s", bulk_path)
        start = time.time()

        # Read bulk data
        if bulk_path.suffix == ".parquet":
            bulk_df = pl.read_parquet(bulk_path)
        elif bulk_path.suffix == ".csv":
            bulk_df = pl.read_csv(bulk_path)
        else:
            raise ValueError(f"Unsupported bulk file format: {bulk_path.suffix}")

        logger.info("Loaded %d records from bulk data", len(bulk_df))

        # Select only the base columns that exist in both datasets
        base_columns = [
            "event_id",
            "user_id",
            "timestamp",
            "page_url",
            "country",
            "device",
            "ip_address",
        ]

        # Filter to only columns that exist in both dataframes
        bulk_base_cols = [col for col in base_columns if col in bulk_df.columns]
        incr_base_cols = [col for col in base_columns if col in self.df.columns]

        # Use the intersection of columns
        common_cols = list(set(bulk_base_cols) & set(incr_base_cols))

        bulk_df = bulk_df.select(common_cols)
        self.df = self.df.select(common_cols)

        # Concatenate bulk and incremental data
        combined_df = pl.concat([bulk_df, self.df])
        logger.info("Combined data: %d records", len(combined_df))

        # Remove duplicates based on event_id (keep latest)
        combined_df = combined_df.unique(subset=["event_id"], keep="last")
        logger.info("After deduplication: %d records", len(combined_df))

        self.df = combined_df
        merge_time = time.time() - start
        self.metrics["merge_time"] = merge_time
        logger.info("Merge completed in %.2fs", merge_time)

        return self.df

    @timed_phase("load", "write")
    def write_output(self, format: str = "parquet") -> Path | str:
        """Write processed data to output.

        Args:
            format: Output format (parquet or csv) - only used if not using Iceberg

        Returns:
            Path to output file or Iceberg table name
        """
        logger.info("Writing output to %s", self.output_path)
        start = time.time()

        if self.use_iceberg:
            # Write to Iceberg table
            output_location = self._write_to_iceberg()
        else:
            # Write to file
            output_file = self.output_path / f"polars_output_{self.mode}.{format}"

            if format == "parquet":
                self.df.write_parquet(output_file)
            elif format == "csv":
                self.df.write_csv(output_file)
            else:
                raise ValueError(f"Unsupported format: {format}")

            output_location = output_file

        self.metrics["write_time"] = time.time() - start
        logger.info(
            "Write completed in %.2fs - Wrote to %s",
            self.metrics["write_time"],
            output_location,
        )

        return output_location

    def _write_to_iceberg(self) -> str:
        """Write data to Iceberg table with proper merge for incremental mode.

        Returns:
            Iceberg table name
        """
        logger.info(
            "Writing to Iceberg table: %s (mode: %s)", self.table_name, self.mode
        )

        # Ensure table exists
        self._create_iceberg_table_if_not_exists()

        # Load the table
        table = self.catalog.load_table(self.table_name)

        # Convert Polars DataFrame to PyArrow Table
        arrow_table = self.df.to_arrow()

        # Fix schema to match Iceberg requirements (make required fields non-nullable)
        # Create new schema with correct nullability
        new_fields = []
        for field in arrow_table.schema:
            if field.name in ["event_id", "user_id", "timestamp"]:
                # Make required fields non-nullable
                new_fields.append(pa.field(field.name, field.type, nullable=False))
            else:
                new_fields.append(field)

        new_schema = pa.schema(new_fields)
        arrow_table = arrow_table.cast(new_schema)

        if self.mode == "bulk":
            # Bulk mode: Overwrite the table
            logger.info("Performing bulk write (overwrite)")
            table.overwrite(arrow_table)
            logger.info("Bulk write completed - %d records written", len(self.df))

        else:  # incremental mode
            # Incremental mode: Merge/upsert based on event_id
            logger.info("Performing incremental merge (upsert on event_id)")

            # PyIceberg doesn't have native merge yet, so we implement it manually:
            # 1. Read existing data
            # 2. Combine with new data
            # 3. Deduplicate by event_id (keeping latest)
            # 4. Overwrite table

            try:
                # Read existing data
                existing_scan = table.scan()
                existing_arrow = existing_scan.to_arrow()
                existing_df = pl.from_arrow(existing_arrow)
                logger.info(
                    "Read %d existing records from Iceberg table", len(existing_df)
                )

                # Ensure both dataframes have the same columns in the same order
                # Get all columns from the new data (which has been sessionized)
                new_columns = self.df.columns

                # Select only these columns from existing data (in case schema evolved)
                existing_columns = [
                    col for col in new_columns if col in existing_df.columns
                ]
                if set(existing_columns) != set(new_columns):
                    logger.warning(
                        "Column mismatch between existing and new data. "
                        "Existing: %s, New: %s",
                        existing_df.columns,
                        new_columns,
                    )
                    # Add missing columns to existing data with null values
                    for col in new_columns:
                        if col not in existing_df.columns:
                            existing_df = existing_df.with_columns(
                                pl.lit(None).alias(col)
                            )

                # Reorder existing data columns to match new data
                existing_df = existing_df.select(new_columns)

                # Combine existing and new data
                combined_df = pl.concat([existing_df, self.df])
                logger.info("Combined data: %d records", len(combined_df))

                # Deduplicate by event_id, keeping the latest (last occurrence)
                merged_df = combined_df.unique(subset=["event_id"], keep="last")
                logger.info("After merge/deduplication: %d records", len(merged_df))

                # Convert to Arrow and overwrite
                merged_arrow = merged_df.to_arrow()

                # Fix schema to match Iceberg requirements
                new_fields = []
                for field in merged_arrow.schema:
                    if field.name in ["event_id", "user_id", "timestamp"]:
                        new_fields.append(
                            pa.field(field.name, field.type, nullable=False)
                        )
                    else:
                        new_fields.append(field)
                new_schema = pa.schema(new_fields)
                merged_arrow = merged_arrow.cast(new_schema)

                table.overwrite(merged_arrow)

                logger.info(
                    "Incremental merge completed - %d new records, %d total records",
                    len(self.df),
                    len(merged_df),
                )

            except Exception as e:
                # If table is empty or read fails, just append
                logger.warning("Could not read existing data, performing append: %s", e)
                table.append(arrow_table)
                logger.info("Appended %d records", len(self.df))

        return self.table_name

    def run_pipeline(
        self, output_format: str = "parquet", bulk_data_path: str | None = None
    ) -> dict[str, Any]:
        """Run the complete ETL pipeline.

        Args:
            output_format: Output format (parquet or csv) - only used if not using Iceberg
            bulk_data_path: Path to bulk data for incremental merge (optional, not used with Iceberg)

        Returns:
            Dictionary with metrics and results
        """
        logger.info("=" * 60)
        logger.info("Running Polars ETL Pipeline - %s mode", self.mode.upper())
        if self.use_iceberg:
            logger.info("Output: Iceberg table %s", self.table_name)
        else:
            logger.info("Output: %s files", output_format)
        logger.info("=" * 60)

        # Start pipeline timing
        self._timer.start_pipeline()

        # Read data
        self.read_data()

        # Apply data quality checks
        self.apply_data_quality()

        # For incremental mode with file-based output, merge with bulk data if provided
        # With Iceberg, the merge happens in the write phase
        if self.mode == "incremental" and bulk_data_path and not self.use_iceberg:
            self.merge_with_bulk(Path(bulk_data_path))
            # Re-apply sessionization after merge
            self.apply_sessionization()
        else:
            # Apply sessionization
            self.apply_sessionization()

        # Write output (handles merge for Iceberg in incremental mode)
        output_location = self.write_output(format=output_format)

        # End pipeline timing
        self._timer.end_pipeline()

        # Update legacy metrics for compatibility
        self.metrics["total_time"] = self._timer.metrics["total_time"]

        logger.info("=" * 60)
        logger.info("Pipeline completed in %.2fs", self.metrics["total_time"])
        logger.info("=" * 60)

        # Log quality report
        if self.quality_report:
            self.quality_report.log_summary()

        # Log timing summary
        self._timer.log_summary()

        return {
            "mode": self.mode,
            "total_time": self.metrics["total_time"],
            "metrics": self.metrics,
            "timing_metrics": self._timer.metrics,
            "records_processed": len(self.df) if self.df is not None else 0,
            "output_location": str(output_location),
            "use_iceberg": self.use_iceberg,
            "quality_report": self.quality_report,
        }


def run_polars_etl(
    input_path: str,
    output_path: str,
    mode: str = "bulk",
    output_format: str = "parquet",
    quality_config: DataQualityConfig | None = None,
    bulk_data_path: str | None = None,
    use_iceberg: bool = True,
    iceberg_config: IcebergConfig | None = None,
) -> dict[str, Any]:
    """Run Polars ETL pipeline.

    Args:
        input_path: Path to input data (file for bulk, directory for incremental)
        output_path: Path to output directory
        mode: Processing mode ('bulk' or 'incremental')
        output_format: Output format ('parquet' or 'csv') - only used if not using Iceberg
        quality_config: Data quality configuration
        bulk_data_path: Path to bulk data for incremental merge (optional, not used with Iceberg)
        use_iceberg: Whether to use Iceberg tables for output
        iceberg_config: Iceberg configuration

    Returns:
        Dictionary with metrics and results
    """
    pipeline = PolarsPipeline(
        input_path, output_path, mode, quality_config, use_iceberg, iceberg_config
    )
    return pipeline.run_pipeline(
        output_format=output_format, bulk_data_path=bulk_data_path
    )


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Polars ETL Pipeline - Bulk and Incremental Processing"
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
        default="data/output/polars",
        help="Output directory (default: data/output/polars)",
    )
    parser.add_argument(
        "--format",
        choices=["parquet", "csv"],
        default="parquet",
        help="Output format (default: parquet) - only used if --no-iceberg is set",
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
        help="Disable Iceberg table output (use Parquet/CSV files instead)",
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
        args.bulk_data = "data/output/polars/polars_output_bulk.parquet"

    use_iceberg = not args.no_iceberg

    logger.info("Starting Polars ETL Pipeline")
    logger.info("Mode: %s", args.mode)
    logger.info("Input: %s", args.input)
    logger.info("Output: %s", args.output)
    logger.info("Use Iceberg: %s", use_iceberg)
    if args.bulk_data:
        logger.info("Bulk data: %s", args.bulk_data)

    start_time = datetime.now()
    results = run_polars_etl(
        input_path=args.input,
        output_path=args.output,
        mode=args.mode,
        output_format=args.format,
        bulk_data_path=args.bulk_data,
        use_iceberg=use_iceberg,
    )
    end_time = datetime.now()

    # Print summary
    print("\n" + "=" * 60)
    print("POLARS ETL SUMMARY")
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
