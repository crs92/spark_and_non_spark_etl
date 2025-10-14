"""Simple clickstream data generator for ETL benchmark testing."""

import random
import uuid
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar

import polars as pl
from faker import Faker


class DataSize(Enum):
    """Data size categories for benchmark testing.

    Attributes:
        SMALL: Small data size.
        MEDIUM: Medium data size.
        LARGE: Large data size.
    """

    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class ClickstreamDataGenerator:
    """Simple clickstream data generator for ETL benchmarking.

    Attributes:
        SIZE_RECORD_COUNTS (ClassVar[dict[DataSize, int]]): Record counts for different data sizes.
        PAGES (ClassVar[list[str]]): List of possible page URLs for clickstream events.
        COUNTRIES (ClassVar[list[str]]): List of possible countries for clickstream events.
        DEVICES (ClassVar[list[str]]): List of possible device types for clickstream events.
    """

    # Record counts for different data sizes
    SIZE_RECORD_COUNTS: ClassVar[dict[DataSize, int]] = {
        DataSize.SMALL: 100_000,
        DataSize.MEDIUM: 10_000_000,
        DataSize.LARGE: 100_000_000,
    }

    # Simple realistic data for clickstream
    PAGES: ClassVar[list[str]] = [
        "/",
        "/home",
        "/products",
        "/about",
        "/contact",
        "/login",
        "/search",
        "/cart",
        "/checkout",
    ]
    COUNTRIES: ClassVar[list[str]] = [
        "US",
        "CA",
        "GB",
        "DE",
        "FR",
        "IT",
        "ES",
        "AU",
        "JP",
    ]
    DEVICES: ClassVar[list[str]] = ["desktop", "mobile", "tablet"]

    def __init__(self, size: DataSize, seed: int | None = None) -> None:
        """Initialize the generator.

        Args:
            size (DataSize): The data size category for generation.
            seed (int | None): Optional random seed for reproducibility.
        """
        self.size = size
        self.record_count = self.SIZE_RECORD_COUNTS[size]
        self.faker = Faker()

        if seed is not None:
            Faker.seed(seed)
            random.seed(seed)

        # Generate a realistic pool of users (much smaller than total events)
        # This creates realistic user behavior patterns for sessionization
        user_count = max(
            100, self.record_count // 1000
        )  # 1 user per 1000 events on average
        self.user_pool = [str(uuid.uuid4()) for _ in range(user_count)]

    def _generate_event(self, timestamp: datetime) -> dict[str, Any]:
        """Generate a single clickstream event.

        Args:
            timestamp (datetime): The timestamp for the generated event.

        Returns:
            dict[str, Any]: A dictionary representing the clickstream event with fields such as event_id, user_id, session_id, timestamp, page_url, country, device, and ip_address.
        """
        # Select a user from the realistic user pool instead of generating random UUIDs
        user_id = random.choice(self.user_pool)  # noqa: S311

        # Generate a temporary session_id that will be replaced by proper sessionization logic in ETL
        # This is kept for backward compatibility but will be ignored by the ETL implementations
        temp_session_id = f"temp_{user_id}_{timestamp.strftime('%Y%m%d_%H')}"

        return {
            "event_id": str(uuid.uuid4()),
            "user_id": user_id,
            "session_id": (
                temp_session_id
            ),  # Temporary - will be replaced by ETL sessionization
            "timestamp": timestamp,
            "page_url": random.choice(self.PAGES),  # noqa: S311
            "country": random.choice(self.COUNTRIES),  # noqa: S311
            "device": random.choice(self.DEVICES),  # noqa: S311
            "ip_address": self.faker.ipv4(),
        }

    def generate_bulk_data(
        self,
        start_date: datetime,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """Generate bulk historical clickstream data with realistic user
        session patterns.

        Args:
            start_date (datetime): The starting date for bulk data generation.
            days (int, optional): Number of days to generate data for. Defaults to 30.

        Returns:
            list[dict[str, Any]]: List of generated clickstream events for the specified date range.
        """
        events = []
        end_date = start_date + timedelta(days=days)

        # Generate events in realistic user session clusters
        remaining_events = self.record_count

        while remaining_events > 0:
            # Select a random user for this session cluster
            user_id = random.choice(self.user_pool)  # noqa: S311

            # Generate a random session start time
            random_seconds = random.randint(  # noqa: S311
                0,
                int((end_date - start_date).total_seconds()),
            )
            session_start = start_date + timedelta(seconds=random_seconds)

            # Generate 1-20 events for this user session cluster
            events_in_cluster = min(
                remaining_events, random.randint(1, 20)  # noqa: S311
            )

            current_time = session_start
            for i in range(events_in_cluster):
                # Create event at current time
                event = self._generate_event(current_time)
                event["user_id"] = user_id  # Ensure consistent user_id for the cluster
                events.append(event)

                # Move to next event time within the cluster
                if i < events_in_cluster - 1:  # Not the last event
                    # 70% chance of staying in same session (< 30 min gap)
                    # 30% chance of creating session boundary (> 30 min gap)
                    if random.random() < 0.7:  # noqa: S311
                        # Stay in session: 1-29 minute gap
                        gap_minutes = random.randint(1, 29)  # noqa: S311
                    else:
                        # Create session boundary: 31-120 minute gap
                        gap_minutes = random.randint(31, 120)  # noqa: S311

                    current_time += timedelta(minutes=gap_minutes)

                    # Ensure we don't exceed the date range
                    if current_time > end_date:
                        break

            remaining_events -= events_in_cluster

        return events

    def generate_incremental_data(
        self,
        date: datetime,
        records_per_day: int = 1000,
    ) -> list[dict[str, Any]]:
        """Generate incremental data for a specific day with realistic user
        session patterns.

        Args:
            date (datetime): The date for which to generate data.
            records_per_day (int, optional): The number of records to generate for the day. Defaults to 1000.

        Returns:
            list[dict[str, Any]]: List of generated clickstream events for the day.
        """
        events = []
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        # Generate events in realistic user session clusters
        remaining_events = records_per_day

        while remaining_events > 0:
            # Select a random user for this session cluster
            user_id = random.choice(self.user_pool)  # noqa: S311

            # Generate a random session start time within the day
            random_seconds = random.randint(0, 86400)  # noqa: S311
            session_start = start_of_day + timedelta(seconds=random_seconds)

            # Generate 1-10 events for this user session cluster (smaller for daily data)
            events_in_cluster = min(
                remaining_events, random.randint(1, 10)  # noqa: S311
            )

            current_time = session_start
            for i in range(events_in_cluster):
                # Create event at current time
                event = self._generate_event(current_time)
                event["user_id"] = user_id  # Ensure consistent user_id for the cluster
                events.append(event)

                # Move to next event time within the cluster
                if i < events_in_cluster - 1:  # Not the last event
                    # 80% chance of staying in same session (< 30 min gap)
                    # 20% chance of creating session boundary (> 30 min gap)
                    if random.random() < 0.8:  # noqa: S311
                        # Stay in session: 1-29 minute gap
                        gap_minutes = random.randint(1, 29)  # noqa: S311
                    else:
                        # Create session boundary: 31-120 minute gap
                        gap_minutes = random.randint(31, 120)  # noqa: S311

                    current_time += timedelta(minutes=gap_minutes)

                    # Ensure we don't exceed the day
                    if current_time >= end_of_day:
                        break

            remaining_events -= events_in_cluster

        return events


def generate_benchmark_data(
    size: str,
    output_dir: str,
    formats: list[str] | None = None,
    seed: int | None = None,
    incremental_days: int = 7,
) -> dict[str, Any]:
    """Generate ETL benchmark data: bulk load + incremental files.

    Args:
        size (str): Data size ('small', 'medium', 'large')
        output_dir (str): Directory to save generated files
        formats (list[str] | None): List of formats to generate ('csv', 'parquet')
        seed (int | None): Random seed for reproducible generation
        incremental_days (int): Number of incremental daily files to generate

    Returns:
        (dict[str, Any]): Dictionary with generation results and file paths

    Raises:
        ValueError: If invalid size or unsupported format is provided

    """
    if formats is None:
        formats = ["csv", "parquet"]

    # Validate inputs
    try:
        data_size = DataSize(size)
    except ValueError as e:
        msg = f"Invalid size. Must be one of {[s.value for s in DataSize]}"
        raise ValueError(msg) from e

    supported_formats = {"csv", "parquet"}
    invalid_formats = set(formats) - supported_formats
    if invalid_formats:
        msg = f"Unsupported formats: {invalid_formats}. Supported: {supported_formats}"
        raise ValueError(
            msg,
        )

    # Create output directory structure
    output_path = Path(output_dir)
    bulk_dir = output_path / "bulk"
    incremental_dir = output_path / "incremental"

    bulk_dir.mkdir(parents=True, exist_ok=True)
    incremental_dir.mkdir(parents=True, exist_ok=True)

    # Initialize generator
    generator = ClickstreamDataGenerator(data_size, seed=seed)

    # Generate bulk data (30 days of historical data)
    bulk_start_date = datetime(2024, 1, 1)
    bulk_events = generator.generate_bulk_data(bulk_start_date, days=30)

    # Generate incremental data (daily files)
    incremental_start_date = datetime(2024, 2, 1)

    results = {
        "size": size,
        "bulk_record_count": len(bulk_events),
        "incremental_days": incremental_days,
        "files": {},
    }

    for format_type in formats:
        format_results = {"bulk": {}, "incremental": []}

        # Save bulk data
        bulk_filename = f"bulk_data_{size}.{format_type}"
        bulk_file_path = bulk_dir / bulk_filename

        df_bulk = pl.DataFrame(bulk_events)
        if format_type == "csv":
            df_bulk.write_csv(bulk_file_path)
        else:  # parquet
            df_bulk.write_parquet(bulk_file_path)

        format_results["bulk"] = {
            "path": str(bulk_file_path),
            "records": len(bulk_events),
            "size_mb": bulk_file_path.stat().st_size / (1024 * 1024),
        }

        # Save incremental data (daily files)
        for day in range(incremental_days):
            current_date = incremental_start_date + timedelta(days=day)
            date_str = current_date.strftime("%Y-%m-%d")

            # Generate daily incremental data
            daily_events = generator.generate_incremental_data(current_date)

            incremental_filename = f"incremental_{date_str}_{size}.{format_type}"
            incremental_file_path = incremental_dir / incremental_filename

            df_incremental = pl.DataFrame(daily_events)
            if format_type == "csv":
                df_incremental.write_csv(incremental_file_path)
            else:  # parquet
                df_incremental.write_parquet(incremental_file_path)

            format_results["incremental"].append(
                {
                    "date": date_str,
                    "path": str(incremental_file_path),
                    "records": len(daily_events),
                    "size_mb": incremental_file_path.stat().st_size / (1024 * 1024),
                },
            )

        results["files"][format_type] = format_results

    return results
