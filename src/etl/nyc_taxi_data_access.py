"""NYC Taxi data access module.

This module provides utilities for reading NYC Taxi data from the public
S3 bucket, handling schema evolution across years, and validating data
quality.
"""

import logging
from typing import Any

import polars as pl

from src.etl.nyc_taxi_config import (
    SCHEMA_MAPPING,
    DataSize,
    NYCTaxiDataset,
    get_dataset_config,
)

logger = logging.getLogger(__name__)


class NYCTaxiDataReader:
    """Reader for NYC Taxi public dataset with schema evolution handling."""

    def __init__(self, dataset_config: NYCTaxiDataset):
        """Initialize the data reader.

        Args:
            dataset_config: Configuration for the dataset to read
        """
        self.config = dataset_config
        self.files = dataset_config.get_file_list()
        logger.info(
            "Initialized NYC Taxi reader for %s (%s)",
            self.config.name,
            self.config.time_range,
        )
        logger.info("Will read %d files", len(self.files))

    def read_with_polars(self) -> pl.DataFrame:
        """Read NYC Taxi data using Polars.

        Returns:
            Polars DataFrame with standardized schema

        Raises:
            ValueError: If no valid data could be read
        """
        logger.info("Reading NYC Taxi data with Polars...")
        logger.info("Files to read: %d", len(self.files))

        dfs = []
        successful_reads = 0
        failed_reads = 0

        for file_path in self.files:
            try:
                # Read parquet file from S3
                df = pl.read_parquet(file_path)
                logger.debug("Successfully read %s (%d records)", file_path, len(df))

                # Standardize schema
                df = self._standardize_schema_polars(df)

                dfs.append(df)
                successful_reads += 1

            except Exception as e:
                logger.warning("Failed to read %s: %s", file_path, e)
                failed_reads += 1
                # Continue to next file

        if not dfs:
            raise ValueError(
                "Failed to read any data files. "
                f"Attempted: {len(self.files)}, Failed: {failed_reads}"
            )

        logger.info("Successfully read %d/%d files", successful_reads, len(self.files))

        # Concatenate all dataframes
        combined_df = pl.concat(dfs)
        logger.info("Combined dataset: %d records", len(combined_df))

        # Validate data
        self._validate_data_polars(combined_df)

        return combined_df

    def _standardize_schema_polars(self, df: pl.DataFrame) -> pl.DataFrame:
        """Standardize schema to handle evolution across years.

        Args:
            df: Input DataFrame with potentially different column names

        Returns:
            DataFrame with standardized column names
        """
        # Map columns to standard names
        rename_map = {}

        for standard_name, possible_names in SCHEMA_MAPPING.items():
            for possible_name in possible_names:
                if possible_name in df.columns:
                    if possible_name != standard_name:
                        rename_map[possible_name] = standard_name
                    break

        if rename_map:
            df = df.rename(rename_map)
            logger.debug("Renamed columns: %s", rename_map)

        # Select only the columns we need
        required_columns = [
            "pickup_datetime",
            "dropoff_datetime",
            "passenger_count",
            "trip_distance",
            "pickup_location_id",
            "dropoff_location_id",
            "fare_amount",
            "total_amount",
        ]

        # Filter to only columns that exist
        available_columns = [col for col in required_columns if col in df.columns]

        if not available_columns:
            logger.warning(
                "No standard columns found in DataFrame. Available: %s", df.columns
            )

        return df.select(available_columns)

    def _validate_data_polars(self, df: pl.DataFrame) -> None:
        """Validate data quality.

        Args:
            df: DataFrame to validate

        Raises:
            ValueError: If data validation fails
        """
        if len(df) == 0:
            raise ValueError("DataFrame is empty")

        # Check for required columns
        required_columns = ["pickup_datetime", "trip_distance", "fare_amount"]
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")

        # Log data quality metrics
        total_records = len(df)

        for col in required_columns:
            null_count = df.filter(pl.col(col).is_null()).height
            if null_count > 0:
                null_pct = (null_count / total_records) * 100
                logger.warning(
                    "Column '%s' has %d null values (%.2f%%)",
                    col,
                    null_count,
                    null_pct,
                )

        logger.info("Data validation passed")

    def get_metadata(self) -> dict[str, Any]:
        """Get metadata about the dataset.

        Returns:
            Dictionary with dataset metadata
        """
        return {
            "name": self.config.name,
            "time_range": self.config.time_range,
            "start_date": self.config.start_date,
            "end_date": self.config.end_date,
            "approx_size_gb": self.config.approx_size_gb,
            "approx_records": self.config.approx_records,
            "file_count": len(self.files),
            "files": self.files,
        }


def read_nyc_taxi_data(
    size: DataSize | str, framework: str = "polars"
) -> pl.DataFrame | Any:
    """Read NYC Taxi data for the specified size.

    Args:
        size: Dataset size (DataSize enum or string)
        framework: Framework to use ('polars' or 'spark')

    Returns:
        DataFrame with NYC Taxi data

    Raises:
        ValueError: If framework is not supported or data cannot be read
    """
    config = get_dataset_config(size)
    reader = NYCTaxiDataReader(config)

    if framework.lower() == "polars":
        return reader.read_with_polars()
    if framework.lower() == "spark":
        raise NotImplementedError(
            "Spark reading will be implemented in spark_etl_nyc_taxi.py"
        )
    raise ValueError(f"Unsupported framework: {framework}")
