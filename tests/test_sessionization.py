"""Test sessionization logic in both ETL implementations."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl
import pytest
from pyspark.sql import SparkSession

from src.etl.non_spark_etl import run_non_spark_etl
from src.etl.spark_etl import run_spark_etl


@pytest.fixture
def spark_session():
    """Create a Spark session for testing."""
    spark = (
        SparkSession.builder.appName("SessionizationTest")
        .master("local[*]")
        .getOrCreate()
    )
    yield spark
    spark.stop()


def create_test_data():
    """Create test data with known sessionization patterns."""
    base_time = datetime(2024, 1, 1, 10, 0, 0)

    # Create test events with specific timing patterns
    events = [
        # User 1: Single session (events within 30 minutes)
        {
            "event_id": "e1",
            "user_id": "user1",
            "timestamp": base_time,
            "page_url": "/home",
            "device": "desktop",
            "ip_address": "192.168.1.1",
        },
        {
            "event_id": "e2",
            "user_id": "user1",
            "timestamp": base_time + timedelta(minutes=10),
            "page_url": "/products",
            "device": "desktop",
            "ip_address": "192.168.1.1",
        },
        {
            "event_id": "e3",
            "user_id": "user1",
            "timestamp": base_time + timedelta(minutes=20),
            "page_url": "/cart",
            "device": "desktop",
            "ip_address": "192.168.1.1",
        },
        # User 1: New session (gap > 30 minutes)
        {
            "event_id": "e4",
            "user_id": "user1",
            "timestamp": base_time + timedelta(minutes=60),
            "page_url": "/home",
            "device": "desktop",
            "ip_address": "192.168.1.1",
        },
        {
            "event_id": "e5",
            "user_id": "user1",
            "timestamp": base_time + timedelta(minutes=65),
            "page_url": "/about",
            "device": "desktop",
            "ip_address": "192.168.1.1",
        },
        # User 2: Single session
        {
            "event_id": "e6",
            "user_id": "user2",
            "timestamp": base_time + timedelta(minutes=5),
            "page_url": "/home",
            "device": "mobile",
            "ip_address": "192.168.1.2",
        },
        {
            "event_id": "e7",
            "user_id": "user2",
            "timestamp": base_time + timedelta(minutes=15),
            "page_url": "/search",
            "device": "mobile",
            "ip_address": "192.168.1.2",
        },
    ]

    return events


def test_polars_sessionization():
    """Test sessionization logic in Polars implementation."""
    events = create_test_data()

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test input file
        input_dir = Path(temp_dir) / "input"
        input_dir.mkdir()
        input_file = input_dir / "sample_data.csv"

        # Write test data
        df = pl.DataFrame(events)
        df.write_csv(input_file)

        # Run ETL
        output_dir = Path(temp_dir) / "output"
        result_file = run_non_spark_etl(str(input_dir), str(output_dir))

        # Read and verify results
        result_df = pl.read_parquet(result_file)

        # Verify sessionization
        user1_sessions = (
            result_df.filter(pl.col("user_id") == "user1")["session_id"]
            .unique()
            .to_list()
        )
        user2_sessions = (
            result_df.filter(pl.col("user_id") == "user2")["session_id"]
            .unique()
            .to_list()
        )

        # User 1 should have 2 sessions (gap > 30 minutes)
        assert (
            len(user1_sessions) == 2
        ), f"User1 should have 2 sessions, got {len(user1_sessions)}"

        # User 2 should have 1 session (all events within 30 minutes)
        assert (
            len(user2_sessions) == 1
        ), f"User2 should have 1 session, got {len(user2_sessions)}"

        # Verify session duration calculation
        session_durations = result_df.select(
            "session_id", "session_duration_minutes"
        ).unique()
        assert all(
            duration >= 0
            for duration in session_durations["session_duration_minutes"].to_list()
        )


def test_spark_sessionization(spark_session):
    """Test sessionization logic in Spark implementation."""
    events = create_test_data()

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test input file
        input_dir = Path(temp_dir) / "input"
        input_dir.mkdir()
        input_file = input_dir / "sample_data.csv"

        # Write test data
        df = pl.DataFrame(events)
        df.write_csv(input_file)

        # Run ETL
        output_dir = Path(temp_dir) / "output"
        result_file = run_spark_etl(str(input_dir), str(output_dir))

        # Read and verify results using Polars (easier for testing)
        output_parquet_dir = Path(output_dir) / "spark_output"
        parquet_files = list(output_parquet_dir.glob("*.parquet"))
        assert len(parquet_files) > 0, "No parquet files found in output"

        result_df = pl.read_parquet(parquet_files[0])

        # Verify sessionization
        user1_sessions = (
            result_df.filter(pl.col("user_id") == "user1")["session_id"]
            .unique()
            .to_list()
        )
        user2_sessions = (
            result_df.filter(pl.col("user_id") == "user2")["session_id"]
            .unique()
            .to_list()
        )

        # User 1 should have 2 sessions (gap > 30 minutes)
        assert (
            len(user1_sessions) == 2
        ), f"User1 should have 2 sessions, got {len(user1_sessions)}"

        # User 2 should have 1 session (all events within 30 minutes)
        assert (
            len(user2_sessions) == 1
        ), f"User2 should have 1 session, got {len(user2_sessions)}"

        # Verify session duration calculation
        session_durations = result_df.select(
            "session_id", "session_duration_minutes"
        ).unique()
        assert all(
            duration >= 0
            for duration in session_durations["session_duration_minutes"].to_list()
        )


def test_sessionization_equivalence():
    """Test that both implementations produce equivalent sessionization
    results."""
    events = create_test_data()

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test input file
        input_dir = Path(temp_dir) / "input"
        input_dir.mkdir()
        input_file = input_dir / "sample_data.csv"

        # Write test data
        df = pl.DataFrame(events)
        df.write_csv(input_file)

        # Run both ETL implementations
        polars_output_dir = Path(temp_dir) / "polars_output"
        spark_output_dir = Path(temp_dir) / "spark_output"

        polars_result = run_non_spark_etl(str(input_dir), str(polars_output_dir))
        spark_result = run_spark_etl(str(input_dir), str(spark_output_dir))

        # Read results
        polars_df = pl.read_parquet(polars_result)

        spark_parquet_dir = Path(spark_output_dir) / "spark_output"
        spark_parquet_files = list(spark_parquet_dir.glob("*.parquet"))
        spark_df = pl.read_parquet(spark_parquet_files[0])

        # Sort both dataframes for comparison
        polars_df = polars_df.sort(["user_id", "timestamp"])
        spark_df = spark_df.sort(["user_id", "timestamp"])

        # Compare session counts per user
        polars_sessions = (
            polars_df.group_by("user_id")
            .agg(pl.col("session_id").n_unique().alias("session_count"))
            .sort("user_id")
        )

        spark_sessions = (
            spark_df.group_by("user_id")
            .agg(pl.col("session_id").n_unique().alias("session_count"))
            .sort("user_id")
        )

        # Session counts should be identical
        assert polars_sessions.equals(
            spark_sessions
        ), "Session counts differ between implementations"
