"""Data quality and validation utilities for ETL pipelines.

This module provides shared data cleansing, type casting, and validation
logic to ensure consistency between Spark and Polars ETL
implementations.
"""

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class DataQualityIssue(Enum):
    """Types of data quality issues that can be detected."""

    NULL_VALUE = "null_value"
    INVALID_TYPE = "invalid_type"
    OUT_OF_RANGE = "out_of_range"
    INVALID_FORMAT = "invalid_format"
    DUPLICATE = "duplicate"


@dataclass
class DataQualityReport:
    """Report of data quality checks and cleansing operations.

    Attributes:
        total_records: Total number of records processed
        records_with_issues: Number of records with quality issues
        records_dropped: Number of records dropped due to critical issues
        records_corrected: Number of records with corrected values
        null_counts: Dictionary of null counts per column
        type_errors: Dictionary of type casting errors per column
        validation_errors: Dictionary of validation errors per column
    """

    total_records: int
    records_with_issues: int
    records_dropped: int
    records_corrected: int
    null_counts: dict[str, int]
    type_errors: dict[str, int]
    validation_errors: dict[str, int]

    def log_summary(self) -> None:
        """Log a summary of the data quality report."""
        logger.info("=" * 60)
        logger.info("Data Quality Report")
        logger.info("=" * 60)
        logger.info(f"Total records processed: {self.total_records:,}")
        logger.info(f"Records with issues: {self.records_with_issues:,}")
        logger.info(f"Records dropped: {self.records_dropped:,}")
        logger.info(f"Records corrected: {self.records_corrected:,}")

        if self.null_counts:
            logger.info("\nNull value counts:")
            for col, count in sorted(self.null_counts.items()):
                if count > 0:
                    pct = (count / self.total_records) * 100
                    logger.info(f"  {col}: {count:,} ({pct:.2f}%)")

        if self.type_errors:
            logger.info("\nType casting errors:")
            for col, count in sorted(self.type_errors.items()):
                if count > 0:
                    logger.info(f"  {col}: {count:,}")

        if self.validation_errors:
            logger.info("\nValidation errors:")
            for rule, count in sorted(self.validation_errors.items()):
                if count > 0:
                    logger.info(f"  {rule}: {count:,}")

        logger.info("=" * 60)


class DataQualityConfig:
    """Configuration for data quality checks and cleansing operations.

    Attributes:
        drop_null_event_id: Drop records with null event_id
        drop_null_user_id: Drop records with null user_id
        drop_null_timestamp: Drop records with null timestamp
        drop_invalid_timestamps: Drop records with invalid timestamp formats
        drop_duplicate_event_ids: Drop duplicate event IDs
        fill_null_country: Fill null country values with default
        fill_null_device: Fill null device values with default
        validate_ip_format: Validate IP address format
        validate_url_format: Validate URL format
        default_country: Default value for null countries
        default_device: Default value for null devices
    """

    def __init__(
        self,
        drop_null_event_id: bool = True,
        drop_null_user_id: bool = True,
        drop_null_timestamp: bool = True,
        drop_invalid_timestamps: bool = True,
        drop_duplicate_event_ids: bool = True,
        fill_null_country: bool = True,
        fill_null_device: bool = True,
        validate_ip_format: bool = True,
        validate_url_format: bool = True,
        default_country: str = "UNKNOWN",
        default_device: str = "unknown",
    ):
        """Initialize data quality configuration.

        Args:
            drop_null_event_id: Drop records with null event_id
            drop_null_user_id: Drop records with null user_id
            drop_null_timestamp: Drop records with null timestamp
            drop_invalid_timestamps: Drop records with invalid timestamp formats
            drop_duplicate_event_ids: Drop duplicate event IDs
            fill_null_country: Fill null country values with default
            fill_null_device: Fill null device values with default
            validate_ip_format: Validate IP address format
            validate_url_format: Validate URL format
            default_country: Default value for null countries
            default_device: Default value for null devices
        """
        self.drop_null_event_id = drop_null_event_id
        self.drop_null_user_id = drop_null_user_id
        self.drop_null_timestamp = drop_null_timestamp
        self.drop_invalid_timestamps = drop_invalid_timestamps
        self.drop_duplicate_event_ids = drop_duplicate_event_ids
        self.fill_null_country = fill_null_country
        self.fill_null_device = fill_null_device
        self.validate_ip_format = validate_ip_format
        self.validate_url_format = validate_url_format
        self.default_country = default_country
        self.default_device = default_device


# Expected schema definition
EXPECTED_SCHEMA = {
    "event_id": "string",
    "user_id": "string",
    "session_id": "string",
    "timestamp": "datetime",
    "page_url": "string",
    "country": "string",
    "device": "string",
    "ip_address": "string",
}

# Required columns that cannot be null
REQUIRED_COLUMNS = ["event_id", "user_id", "timestamp"]

# Columns that can have default values
FILLABLE_COLUMNS = {
    "country": "UNKNOWN",
    "device": "unknown",
    "page_url": "/unknown",
}
