"""NYC Taxi data access configuration and utilities.

This module provides configuration and utilities for accessing the NYC
Taxi public dataset from S3, handling schema evolution, and defining
data size configurations for benchmarking.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class DataSize(Enum):
    """Predefined data size configurations for benchmarking."""

    TINY = "tiny"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    XLARGE = "xlarge"
    XXLARGE = "xxlarge"


@dataclass
class NYCTaxiDataset:
    """Configuration for a NYC Taxi dataset."""

    name: str
    time_range: str
    start_date: str  # Format: YYYY-MM
    end_date: str  # Format: YYYY-MM
    approx_size_gb: float
    approx_records: int

    def get_file_list(self) -> list[str]:
        """Generate list of S3 file paths for this dataset.

        Returns:
            List of S3 paths to parquet files
        """
        files = []
        start = datetime.strptime(self.start_date, "%Y-%m")
        end = datetime.strptime(self.end_date, "%Y-%m")

        current = start
        while current <= end:
            year_month = current.strftime("%Y-%m")
            # NYC TLC uses yellow_tripdata prefix
            file_path = f"s3://nyc-tlc/trip data/yellow_tripdata_{year_month}.parquet"
            files.append(file_path)

            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)

        return files


# Predefined dataset configurations for benchmarking
DATASETS = {
    DataSize.TINY: NYCTaxiDataset(
        name="tiny",
        time_range="2022-01 (1 month)",
        start_date="2022-01",
        end_date="2022-01",
        approx_size_gb=0.1,
        approx_records=3_000_000,
    ),
    DataSize.SMALL: NYCTaxiDataset(
        name="small",
        time_range="2022 (1 year)",
        start_date="2022-01",
        end_date="2022-12",
        approx_size_gb=1.2,
        approx_records=40_000_000,
    ),
    DataSize.MEDIUM: NYCTaxiDataset(
        name="medium",
        time_range="2020-2022 (3 years)",
        start_date="2020-01",
        end_date="2022-12",
        approx_size_gb=4.0,
        approx_records=120_000_000,
    ),
    DataSize.LARGE: NYCTaxiDataset(
        name="large",
        time_range="2018-2022 (5 years)",
        start_date="2018-01",
        end_date="2022-12",
        approx_size_gb=10.0,
        approx_records=200_000_000,
    ),
    DataSize.XLARGE: NYCTaxiDataset(
        name="xlarge",
        time_range="2015-2022 (8 years)",
        start_date="2015-01",
        end_date="2022-12",
        approx_size_gb=50.0,
        approx_records=500_000_000,
    ),
    DataSize.XXLARGE: NYCTaxiDataset(
        name="xxlarge",
        time_range="2009-2022 (14 years)",
        start_date="2009-01",
        end_date="2022-12",
        approx_size_gb=100.0,
        approx_records=1_000_000_000,
    ),
}


# Schema mapping for NYC Taxi data across different years
# The schema has evolved over time, so we need to handle different column names
SCHEMA_MAPPING = {
    # Standard column names we'll use internally
    "pickup_datetime": ["tpep_pickup_datetime", "pickup_datetime"],
    "dropoff_datetime": ["tpep_dropoff_datetime", "dropoff_datetime"],
    "passenger_count": ["passenger_count"],
    "trip_distance": ["trip_distance"],
    "pickup_location_id": ["PULocationID", "pickup_location_id"],
    "dropoff_location_id": ["DOLocationID", "dropoff_location_id"],
    "fare_amount": ["fare_amount"],
    "total_amount": ["total_amount"],
}


def get_dataset_config(size: DataSize | str) -> NYCTaxiDataset:
    """Get dataset configuration by size.

    Args:
        size: DataSize enum or string name

    Returns:
        NYCTaxiDataset configuration

    Raises:
        ValueError: If size is not recognized
    """
    if isinstance(size, str):
        try:
            size = DataSize(size.lower())
        except ValueError as e:
            valid_sizes = [s.value for s in DataSize]
            raise ValueError(
                f"Invalid size '{size}'. Valid sizes: {valid_sizes}"
            ) from e

    return DATASETS[size]
