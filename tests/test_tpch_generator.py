"""Tests for TPC-H data generator.

This module contains unit tests for the TPCHGenerator class.
"""

import pytest

from src.generation.tpch_generator import TPCHGenerator


class TestTPCHGeneratorInitialization:
    """Tests for TPCHGenerator initialization and validation."""

    def test_valid_initialization(self):
        """Test that generator initializes with valid parameters."""
        generator = TPCHGenerator(
            scale_factor=10, s3_bucket="test-bucket", s3_prefix="test-prefix"
        )

        assert generator.scale_factor == 10
        assert generator.s3_bucket == "test-bucket"
        assert generator.s3_prefix == "test-prefix"
        assert generator.conn is None  # Connection not established yet

    def test_scale_factor_validation_negative(self):
        """Test that negative scale factor raises ValueError."""
        with pytest.raises(ValueError, match="Scale factor must be a positive integer"):
            TPCHGenerator(
                scale_factor=-1, s3_bucket="test-bucket", s3_prefix="test-prefix"
            )

    def test_scale_factor_validation_zero(self):
        """Test that zero scale factor raises ValueError."""
        with pytest.raises(ValueError, match="Scale factor must be a positive integer"):
            TPCHGenerator(
                scale_factor=0, s3_bucket="test-bucket", s3_prefix="test-prefix"
            )

    def test_scale_factor_validation_non_integer(self):
        """Test that non-integer scale factor raises ValueError."""
        with pytest.raises(ValueError, match="Scale factor must be a positive integer"):
            TPCHGenerator(
                scale_factor=10.5, s3_bucket="test-bucket", s3_prefix="test-prefix"
            )

    def test_s3_prefix_trailing_slash_removed(self):
        """Test that trailing slash is removed from S3 prefix."""
        generator = TPCHGenerator(
            scale_factor=10, s3_bucket="test-bucket", s3_prefix="test-prefix/"
        )

        assert generator.s3_prefix == "test-prefix"

    def test_tpch_tables_constant(self):
        """Test that TPCH_TABLES constant contains all 8 tables."""
        expected_tables = [
            "customer",
            "lineitem",
            "nation",
            "orders",
            "part",
            "partsupp",
            "region",
            "supplier",
        ]

        assert expected_tables == TPCHGenerator.TPCH_TABLES
        assert len(TPCHGenerator.TPCH_TABLES) == 8

    def test_context_manager_support(self):
        """Test that generator supports context manager protocol."""
        with TPCHGenerator(
            scale_factor=10, s3_bucket="test-bucket", s3_prefix="test-prefix"
        ) as generator:
            assert generator is not None
            assert isinstance(generator, TPCHGenerator)

        # Connection should be closed after context exit
        assert generator.conn is None


class TestTPCHGeneratorValidation:
    """Tests for table name validation."""

    def test_invalid_table_name_raises_error(self):
        """Test that invalid table name raises ValueError."""
        generator = TPCHGenerator(
            scale_factor=10, s3_bucket="test-bucket", s3_prefix="test-prefix"
        )

        with pytest.raises(ValueError, match="Invalid table name"):
            generator.generate_table("invalid_table")

    def test_valid_table_names(self):
        """Test that all valid table names are in TPCH_TABLES constant."""
        # Just verify the table names are correct
        valid_tables = [
            "customer",
            "lineitem",
            "nation",
            "orders",
            "part",
            "partsupp",
            "region",
            "supplier",
        ]

        for table_name in valid_tables:
            assert table_name in TPCHGenerator.TPCH_TABLES
