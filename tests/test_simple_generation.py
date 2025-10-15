"""Tests for simplified data generation."""

import tempfile
from pathlib import Path

import polars as pl
import pytest

from src.data_generation.generator import generate_benchmark_data


def test_generate_small_benchmark_data():
    """Test small benchmark data generation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        result = generate_benchmark_data(
            size="small",
            complexity="simple",
            output_dir=temp_dir,
            formats=["csv"],
            seed=42,
        )

        # Check result metadata
        assert result["record_count"] > 0
        assert result["size"] == "small"
        assert result["complexity"] == "simple"
        assert "files" in result
        assert "csv" in result["files"]

        # Check file was created
        csv_path = Path(result["files"]["csv"]["path"])
        assert csv_path.exists()

        # Load and validate data
        df = pl.read_csv(csv_path)
        assert len(df) == result["record_count"]

        # Check required columns
        required_cols = [
            "event_id",
            "user_id",
            "session_id",
            "timestamp",
            "page_url",
            "ip_address",
            "country",
        ]
        for col in required_cols:
            assert col in df.columns
            assert df[col].null_count() == 0


def test_generate_parquet_format():
    """Test Parquet format generation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        result = generate_benchmark_data(
            size="small",
            complexity="simple",
            output_dir=temp_dir,
            formats=["parquet"],
            seed=42,
        )

        parquet_path = Path(result["files"]["parquet"]["path"])
        assert parquet_path.exists()
        assert result["record_count"] > 0

        # Load and validate Parquet
        df = pl.read_parquet(parquet_path)
        assert len(df) == result["record_count"]


def test_generate_benchmark_data():
    """Test benchmark data generation with predefined sizes."""
    with tempfile.TemporaryDirectory() as temp_dir:
        result = generate_benchmark_data(size="small", output_dir=temp_dir)

        # Check result structure
        assert result["size"] == "small"
        assert result["record_count"] > 0
        assert "files" in result
        assert "csv" in result["files"]
        assert "parquet" in result["files"]

        # Check files exist
        csv_path = Path(result["files"]["csv"]["path"])
        parquet_path = Path(result["files"]["parquet"]["path"])
        assert csv_path.exists()
        assert parquet_path.exists()

        # Validate CSV data
        df_csv = pl.read_csv(csv_path)
        assert len(df_csv) == result["record_count"]

        # Validate Parquet data
        df_parquet = pl.read_parquet(parquet_path)
        assert len(df_parquet) == result["record_count"]

        # Data should be identical between formats
        assert df_csv.equals(df_parquet)


def test_data_sizes():
    """Test that different sizes produce different record counts."""
    with tempfile.TemporaryDirectory() as temp_dir:
        small_result = generate_benchmark_data(
            size="small", complexity="simple", output_dir=temp_dir, seed=42
        )
        medium_result = generate_benchmark_data(
            size="medium", complexity="simple", output_dir=temp_dir, seed=42
        )

        # Sizes should be reasonable and increasing
        assert small_result["record_count"] < medium_result["record_count"]


def test_reproducible_generation():
    """Test that same seed produces identical data."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Generate data twice with same seed
        result1 = generate_benchmark_data(
            size="small",
            complexity="simple",
            output_dir=temp_dir,
            formats=["csv"],
            seed=42,
        )
        result2 = generate_benchmark_data(
            size="small",
            complexity="simple",
            output_dir=temp_dir,
            formats=["csv"],
            seed=42,
        )

        # Should have same record count
        assert result1["record_count"] == result2["record_count"]

        # Load and compare data
        df1 = pl.read_csv(result1["files"]["csv"]["path"])
        df2 = pl.read_csv(result2["files"]["csv"]["path"])

        # Should have same structure
        assert len(df1) == len(df2)
        assert df1.columns == df2.columns


def test_invalid_format():
    """Test error handling for invalid format."""
    with tempfile.TemporaryDirectory() as temp_dir:
        with pytest.raises(ValueError, match="Unsupported formats"):
            generate_benchmark_data(
                size="small",
                complexity="simple",
                output_dir=temp_dir,
                formats=["json"],  # Unsupported format
            )


def test_invalid_size():
    """Test error handling for invalid benchmark size."""
    with tempfile.TemporaryDirectory() as temp_dir:
        with pytest.raises(ValueError, match="Size must be one of"):
            generate_benchmark_data(size="invalid", output_dir=temp_dir)
