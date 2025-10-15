"""Unit tests for data generation framework."""

import tempfile
from datetime import timedelta
from pathlib import Path

import polars as pl
import pytest

from src.data_generation.generator import (
    ClickstreamDataGenerator,
    ComplexityLevel,
    DataCharacteristics,
    DataSize,
    generate_benchmark_data,
)


class TestDataCharacteristics:
    """Test DataCharacteristics configuration."""

    def test_valid_configuration(self):
        """Test valid configuration creation."""
        characteristics = DataCharacteristics(
            size=DataSize.SMALL,
            complexity=ComplexityLevel.SIMPLE,
            skew_factor=0.5,
            join_tables=2,
            temporal_range=timedelta(days=7),
        )

        assert characteristics.size == DataSize.SMALL
        assert characteristics.complexity == ComplexityLevel.SIMPLE
        assert characteristics.skew_factor == 0.5
        assert characteristics.join_tables == 2
        assert characteristics.temporal_range == timedelta(days=7)

    def test_invalid_skew_factor(self):
        """Test validation of skew_factor bounds."""
        with pytest.raises(ValueError, match="skew_factor must be between 0.0 and 1.0"):
            DataCharacteristics(
                size=DataSize.SMALL,
                complexity=ComplexityLevel.SIMPLE,
                skew_factor=1.5,
            )

        with pytest.raises(ValueError, match="skew_factor must be between 0.0 and 1.0"):
            DataCharacteristics(
                size=DataSize.SMALL,
                complexity=ComplexityLevel.SIMPLE,
                skew_factor=-0.1,
            )

    def test_invalid_join_tables(self):
        """Test validation of join_tables."""
        with pytest.raises(ValueError, match="join_tables must be non-negative"):
            DataCharacteristics(
                size=DataSize.SMALL,
                complexity=ComplexityLevel.SIMPLE,
                join_tables=-1,
            )

    def test_invalid_temporal_range(self):
        """Test validation of temporal_range."""
        with pytest.raises(ValueError, match="temporal_range must be positive"):
            DataCharacteristics(
                size=DataSize.SMALL,
                complexity=ComplexityLevel.SIMPLE,
                temporal_range=timedelta(days=-1),
            )


class TestClickstreamDataGenerator:
    """Test ClickstreamDataGenerator functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.characteristics = DataCharacteristics(
            size=DataSize.SMALL,
            complexity=ComplexityLevel.SIMPLE,
        )
        self.generator = ClickstreamDataGenerator(self.characteristics, seed=42)

    def test_initialization(self):
        """Test generator initialization."""
        assert self.generator.characteristics == self.characteristics
        assert self.generator.seed == 42
        assert (
            self.generator.record_count
            == ClickstreamDataGenerator.SIZE_RECORD_COUNTS[DataSize.SMALL][
                ComplexityLevel.SIMPLE
            ]
        )

    def test_custom_record_count(self):
        """Test custom record count override."""
        characteristics = DataCharacteristics(
            size=DataSize.SMALL,
            complexity=ComplexityLevel.SIMPLE,
            record_count=1000,
        )
        generator = ClickstreamDataGenerator(characteristics, seed=42)
        assert generator.record_count == 1000

    def test_weighted_choice_uniform(self):
        """Test uniform distribution (skew_factor=0.0)."""
        values = ["A", "B", "C"]
        results = [self.generator._weighted_choice(values, 0.0) for _ in range(1000)]

        assert len(results) == 1000
        assert all(v in values for v in results)

        # Check distribution is roughly uniform (within 30% tolerance for randomness)
        counts = {v: results.count(v) for v in values}
        expected_count = 1000 / len(values)
        for count in counts.values():
            assert abs(count - expected_count) / expected_count < 0.3

    def test_weighted_choice_skewed(self):
        """Test skewed distribution."""
        characteristics = DataCharacteristics(
            size=DataSize.SMALL,
            complexity=ComplexityLevel.SIMPLE,
            skew_factor=0.8,
        )
        generator = ClickstreamDataGenerator(characteristics, seed=42)

        values = ["A", "B", "C"]
        results = [generator._weighted_choice(values, 0.8) for _ in range(1000)]

        assert len(results) == 1000

        # First value should be most frequent due to skew
        counts = {v: results.count(v) for v in values}
        assert counts["A"] > counts["B"] > counts["C"]

    def test_clickstream_data_generation(self):
        """Test clickstream data generation."""
        events = self.generator.generate_clickstream_data()

        # Should generate approximately the requested number of records (within 20% tolerance)
        assert (
            abs(len(events) - self.generator.record_count) / self.generator.record_count
            < 0.2
        )
        assert all(isinstance(event, dict) for event in events)

        # Check required fields
        required_fields = [
            "event_id",
            "session_id",
            "user_id",
            "timestamp",
            "page_url",
            "ip_address",
        ]
        for event in events[:5]:  # Check first 5
            for field in required_fields:
                assert field in event
                assert event[field] is not None

    def test_join_tables_generation(self):
        """Test join tables generation."""
        characteristics = DataCharacteristics(
            size=DataSize.SMALL,
            complexity=ComplexityLevel.MODERATE,
            join_tables=2,
        )
        generator = ClickstreamDataGenerator(characteristics, seed=42)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            join_tables = generator.generate_join_tables(output_dir, "parquet")

            assert len(join_tables) == 2
            assert all(path.exists() for path in join_tables)
            assert all(path.suffix == ".parquet" for path in join_tables)

            # Verify table contents
            for table_path in join_tables:
                df = pl.read_parquet(table_path)
                assert len(df) > 0
                assert len(df.columns) >= 2


class TestDatasetGeneration:
    """Test complete dataset generation functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.characteristics = DataCharacteristics(
            size=DataSize.SMALL,
            complexity=ComplexityLevel.SIMPLE,
            record_count=1000,  # Small for testing
        )
        self.generator = ClickstreamDataGenerator(self.characteristics, seed=42)

    def test_user_profiles_generation(self):
        """Test user profile generation."""
        profiles = self.generator._generate_user_profiles(100)

        assert len(profiles) == 100

        for profile in profiles[:5]:  # Check first 5
            assert "user_id" in profile
            assert "device_type" in profile
            assert "browser" in profile
            assert "engagement_level" in profile
            assert "country" in profile

            assert profile["device_type"] in ["desktop", "mobile", "tablet"]
            assert profile["browser"] in ["chrome", "firefox", "safari", "edge"]
            assert profile["engagement_level"] in ["low", "medium", "high"]

    def test_session_generation(self):
        """Test session generation."""
        user_profiles = self.generator._generate_user_profiles(10)
        sessions = self.generator._generate_sessions(5, user_profiles)

        assert len(sessions) == 5

        for session in sessions:
            assert "session_id" in session
            assert "user_id" in session
            assert "pages_in_session" in session
            assert "user_profile" in session
            assert session["pages_in_session"] >= 1

    def test_dataset_generation(self):
        """Test complete dataset generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test_clickstream.parquet"

            result = self.generator.generate_dataset(output_path, "parquet")

            assert output_path.exists()
            assert "main_dataset_path" in result
            assert "record_count" in result
            assert "unique_users" in result
            assert "unique_sessions" in result

            # Verify generated data
            df = pl.read_parquet(output_path)
            assert len(df) > 0
            assert len(df) <= self.characteristics.record_count

            # Check required columns
            required_columns = [
                "session_id",
                "user_id",
                "timestamp",
                "page_url",
                "ip_address",
                "user_agent",
                "country",
                "device_type",
            ]
            for col in required_columns:
                assert col in df.columns

            # Check data quality
            assert df["session_id"].null_count() == 0
            assert df["user_id"].null_count() == 0
            assert df["timestamp"].null_count() == 0


class TestBenchmarkDataGeneration:
    """Test benchmark data generation functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)

    def teardown_method(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_generate_benchmark_data(self):
        """Test benchmark data generation function."""
        result = generate_benchmark_data(
            size="small",
            complexity="simple",
            output_dir=str(self.output_dir),
            formats=["csv", "parquet"],
            seed=42,
        )

        assert result["size"] == "small"
        assert result["complexity"] == "simple"
        assert result["record_count"] > 0
        assert "files" in result
        assert "csv" in result["files"]
        assert "parquet" in result["files"]

        # Check files exist
        csv_path = Path(result["files"]["csv"]["path"])
        parquet_path = Path(result["files"]["parquet"]["path"])
        assert csv_path.exists()
        assert parquet_path.exists()

    def test_format_validation(self):
        """Test that only CSV and Parquet formats are supported."""
        with pytest.raises(ValueError, match="Unsupported formats"):
            generate_benchmark_data(
                size="small",
                complexity="simple",
                output_dir=str(self.output_dir),
                formats=["json"],  # Unsupported format
                seed=42,
            )

    def test_invalid_size_complexity(self):
        """Test error handling for invalid size/complexity."""
        with pytest.raises(ValueError, match="Invalid size or complexity"):
            generate_benchmark_data(
                size="invalid",
                complexity="simple",
                output_dir=str(self.output_dir),
                seed=42,
            )


class TestDataGenerationConsistency:
    """Test data generation consistency and reproducibility."""

    def test_reproducible_generation(self):
        """Test that same seed produces consistent data characteristics."""
        characteristics = DataCharacteristics(
            size=DataSize.SMALL,
            complexity=ComplexityLevel.SIMPLE,
            record_count=100,
        )

        # Generate data twice with same seed
        generator1 = ClickstreamDataGenerator(characteristics, seed=42)
        generator2 = ClickstreamDataGenerator(characteristics, seed=42)

        with tempfile.TemporaryDirectory() as temp_dir:
            path1 = Path(temp_dir) / "data1.parquet"
            path2 = Path(temp_dir) / "data2.parquet"

            generator1.generate_dataset(path1)
            generator2.generate_dataset(path2)

            df1 = pl.read_parquet(path1)
            df2 = pl.read_parquet(path2)

            # Should have same structure and size
            assert len(df1) == len(df2)
            assert df1.columns == df2.columns

            # Check that data has consistent characteristics
            assert df1["user_id"].n_unique() == df2["user_id"].n_unique()
            assert df1["session_id"].n_unique() == df2["session_id"].n_unique()

            # Check that both datasets have realistic data
            assert df1["user_id"].n_unique() > 1
            assert df2["user_id"].n_unique() > 1
            assert df1["session_id"].n_unique() > 1
            assert df2["session_id"].n_unique() > 1

            # Check that required columns have no nulls
            for col in ["event_id", "user_id", "session_id", "timestamp", "page_url"]:
                assert df1[col].null_count() == 0
                assert df2[col].null_count() == 0

    def test_different_seeds_produce_different_data(self):
        """Test that different seeds produce different results."""
        characteristics = DataCharacteristics(
            size=DataSize.SMALL,
            complexity=ComplexityLevel.SIMPLE,
            record_count=100,
        )

        generator1 = ClickstreamDataGenerator(characteristics, seed=42)
        generator2 = ClickstreamDataGenerator(characteristics, seed=123)

        with tempfile.TemporaryDirectory() as temp_dir:
            path1 = Path(temp_dir) / "data1.parquet"
            path2 = Path(temp_dir) / "data2.parquet"

            generator1.generate_dataset(path1)
            generator2.generate_dataset(path2)

            df1 = pl.read_parquet(path1)
            df2 = pl.read_parquet(path2)

            # Should be different (at least some values)
            assert len(df1) == len(df2)  # Same size

            # But different content (check timestamps as they're time-based)
            timestamps1 = df1["timestamp"].to_list()
            timestamps2 = df2["timestamp"].to_list()

            # Should have some different timestamps due to different random patterns
            assert timestamps1 != timestamps2

    def test_scalability_across_sizes(self):
        """Test that generator scales appropriately across different data
        sizes."""
        sizes_and_expected_ranges = [
            (DataSize.SMALL, (1000, 500_000)),
            (DataSize.MEDIUM, (500_000, 10_000_000)),
        ]

        for size, (min_records, max_records) in sizes_and_expected_ranges:
            characteristics = DataCharacteristics(
                size=size,
                complexity=ComplexityLevel.SIMPLE,
            )

            generator = ClickstreamDataGenerator(characteristics, seed=42)

            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / f"test_{size.value}.parquet"
                result = generator.generate_dataset(output_path)

                record_count = result["record_count"]
                assert (
                    min_records <= record_count <= max_records
                ), f"Size {size.value} produced {record_count} records"
