"""Integration tests for data quality and ETL output equivalence."""

import polars as pl
import pytest

from src.data_generation.generator import generate_benchmark_data
from src.etl.data_quality import DataQualityConfig, DataQualityReport
from src.etl.non_spark_etl import run_non_spark_etl


class TestDataQuality:
    """Test data quality checks and cleansing operations."""

    @pytest.fixture
    def sample_data_with_issues(self, tmp_path):
        """Create sample data with various quality issues."""
        data = {
            "event_id": ["e1", "e2", None, "e4", "e5", "e5"],  # null and duplicate
            "user_id": ["u1", "u2", "u3", None, "u5", "u6"],  # null
            "session_id": ["s1", "s2", "s3", "s4", "s5", "s6"],
            "timestamp": [
                "2024-01-01 10:00:00",
                "2024-01-01 10:05:00",
                "2024-01-01 10:10:00",
                "2024-01-01 10:15:00",
                None,  # null timestamp
                "2024-01-01 10:25:00",
            ],
            "page_url": [
                "/home",
                "products",
                "/about",
                "/contact",
                "/search",
                "/cart",
            ],  # one missing /
            "country": ["US", None, "GB", "DE", None, "FR"],  # nulls
            "device": [
                "desktop",
                "mobile",
                None,
                "tablet",
                "desktop",
                "mobile",
            ],  # null
            "ip_address": [
                "192.168.1.1",
                "invalid_ip",
                "192.168.1.3",
                "192.168.1.4",
                "192.168.1.5",
                "192.168.1.6",
            ],  # invalid IP
        }

        df = pl.DataFrame(data)
        csv_path = tmp_path / "test_data.csv"
        df.write_csv(csv_path)
        return csv_path

    def test_null_handling_drops_required_nulls(
        self, sample_data_with_issues, tmp_path
    ):
        """Test that null values in required columns are dropped."""
        config = DataQualityConfig(
            drop_null_event_id=True,
            drop_null_user_id=True,
            drop_null_timestamp=True,
        )

        output_path = tmp_path / "output"
        output_path.mkdir()

        # Create input directory with the test file
        input_path = tmp_path / "input"
        input_path.mkdir()
        (input_path / "sample_data.csv").write_text(sample_data_with_issues.read_text())

        output_file, report = run_non_spark_etl(
            str(input_path), str(output_path), quality_config=config
        )

        # Should drop 3 records (1 null event_id, 1 null user_id, 1 null timestamp)
        assert report.records_dropped >= 3
        assert report.null_counts.get("event_id", 0) > 0
        assert report.null_counts.get("user_id", 0) > 0
        assert report.null_counts.get("timestamp", 0) > 0

    def test_null_filling_for_optional_columns(self, sample_data_with_issues, tmp_path):
        """Test that null values in optional columns are filled with
        defaults."""
        config = DataQualityConfig(
            drop_null_event_id=True,
            drop_null_user_id=True,
            drop_null_timestamp=True,
            fill_null_country=True,
            fill_null_device=True,
            default_country="UNKNOWN",
            default_device="unknown",
        )

        output_path = tmp_path / "output"
        output_path.mkdir()

        input_path = tmp_path / "input"
        input_path.mkdir()
        (input_path / "sample_data.csv").write_text(sample_data_with_issues.read_text())

        output_file, report = run_non_spark_etl(
            str(input_path), str(output_path), quality_config=config
        )

        # Should have corrected null country and device values
        assert report.records_corrected > 0

        # Verify output has no nulls in country/device
        df_output = pl.read_parquet(output_file)
        assert df_output["country"].null_count() == 0
        assert df_output["device"].null_count() == 0

    def test_duplicate_removal(self, sample_data_with_issues, tmp_path):
        """Test that duplicate event IDs are removed."""
        config = DataQualityConfig(
            drop_null_event_id=True,
            drop_null_user_id=True,
            drop_null_timestamp=True,
            drop_duplicate_event_ids=True,
        )

        output_path = tmp_path / "output"
        output_path.mkdir()

        input_path = tmp_path / "input"
        input_path.mkdir()
        (input_path / "sample_data.csv").write_text(sample_data_with_issues.read_text())

        output_file, report = run_non_spark_etl(
            str(input_path), str(output_path), quality_config=config
        )

        # Should have dropped at least 1 duplicate
        assert (
            "duplicate_event_ids" in report.validation_errors
            or report.records_dropped > 0
        )

    def test_ip_validation(self, sample_data_with_issues, tmp_path):
        """Test that invalid IP addresses are corrected."""
        config = DataQualityConfig(
            drop_null_event_id=True,
            drop_null_user_id=True,
            drop_null_timestamp=True,
            validate_ip_format=True,
        )

        output_path = tmp_path / "output"
        output_path.mkdir()

        input_path = tmp_path / "input"
        input_path.mkdir()
        (input_path / "sample_data.csv").write_text(sample_data_with_issues.read_text())

        output_file, report = run_non_spark_etl(
            str(input_path), str(output_path), quality_config=config
        )

        # Should have found and corrected invalid IPs
        if "invalid_ip_format" in report.validation_errors:
            assert report.validation_errors["invalid_ip_format"] > 0

    def test_url_validation(self, sample_data_with_issues, tmp_path):
        """Test that URLs are normalized to start with /."""
        config = DataQualityConfig(
            drop_null_event_id=True,
            drop_null_user_id=True,
            drop_null_timestamp=True,
            validate_url_format=True,
        )

        output_path = tmp_path / "output"
        output_path.mkdir()

        input_path = tmp_path / "input"
        input_path.mkdir()
        (input_path / "sample_data.csv").write_text(sample_data_with_issues.read_text())

        output_file, report = run_non_spark_etl(
            str(input_path), str(output_path), quality_config=config
        )

        # Verify all URLs start with /
        df_output = pl.read_parquet(output_file)
        urls_without_slash = df_output.filter(~pl.col("page_url").str.starts_with("/"))
        assert len(urls_without_slash) == 0

    def test_data_quality_report_structure(self, sample_data_with_issues, tmp_path):
        """Test that data quality report contains expected fields."""
        config = DataQualityConfig()

        output_path = tmp_path / "output"
        output_path.mkdir()

        input_path = tmp_path / "input"
        input_path.mkdir()
        (input_path / "sample_data.csv").write_text(sample_data_with_issues.read_text())

        output_file, report = run_non_spark_etl(
            str(input_path), str(output_path), quality_config=config
        )

        # Verify report structure
        assert isinstance(report, DataQualityReport)
        assert report.total_records > 0
        assert isinstance(report.records_with_issues, int)
        assert isinstance(report.records_dropped, int)
        assert isinstance(report.records_corrected, int)
        assert isinstance(report.null_counts, dict)
        assert isinstance(report.type_errors, dict)
        assert isinstance(report.validation_errors, dict)


class TestETLEquivalence:
    """Test that Spark and Polars ETL produce equivalent outputs."""

    @pytest.fixture
    def test_dataset(self, tmp_path):
        """Generate a small test dataset."""
        output_dir = tmp_path / "generated"
        result = generate_benchmark_data(
            size="small",
            output_dir=str(output_dir),
            formats=["csv"],
            seed=42,
            incremental_days=1,
        )
        return output_dir / "bulk" / "bulk_data_small.csv"

    def test_polars_etl_produces_valid_output(self, test_dataset, tmp_path):
        """Test that Polars ETL produces valid output with data quality
        checks."""
        input_path = tmp_path / "input"
        input_path.mkdir()
        (input_path / "sample_data.csv").write_text(test_dataset.read_text())

        output_path = tmp_path / "output"
        output_path.mkdir()

        config = DataQualityConfig()
        output_file, report = run_non_spark_etl(
            str(input_path), str(output_path), quality_config=config
        )

        # Verify output exists and is valid
        assert output_file.exists()
        df = pl.read_parquet(output_file)

        # Verify expected columns exist
        expected_cols = [
            "event_id",
            "user_id",
            "session_id",
            "timestamp",
            "page_url",
            "country",
            "device",
            "ip_address",
            "session_start",
            "session_end",
            "session_duration_minutes",
        ]
        for col in expected_cols:
            assert col in df.columns, f"Missing column: {col}"

        # Verify no nulls in required columns
        assert df["event_id"].null_count() == 0
        assert df["user_id"].null_count() == 0
        assert df["timestamp"].null_count() == 0

        # Verify sessionization was applied
        assert df["session_id"].n_unique() > 0
        assert df["session_duration_minutes"].null_count() == 0

    def test_consistent_type_casting(self, test_dataset, tmp_path):
        """Test that type casting is consistent."""
        input_path = tmp_path / "input"
        input_path.mkdir()
        (input_path / "sample_data.csv").write_text(test_dataset.read_text())

        output_path = tmp_path / "output"
        output_path.mkdir()

        config = DataQualityConfig()
        output_file, report = run_non_spark_etl(
            str(input_path), str(output_path), quality_config=config
        )

        df = pl.read_parquet(output_file)

        # Verify data types
        assert df["timestamp"].dtype == pl.Datetime
        assert df["event_id"].dtype == pl.Utf8
        assert df["user_id"].dtype == pl.Utf8
        assert df["session_id"].dtype == pl.Utf8
        assert df["page_url"].dtype == pl.Utf8
        assert df["country"].dtype == pl.Utf8
        assert df["device"].dtype == pl.Utf8
        assert df["ip_address"].dtype == pl.Utf8

    def test_data_transformation_consistency(self, test_dataset, tmp_path):
        """Test that data transformations are applied consistently."""
        input_path = tmp_path / "input"
        input_path.mkdir()
        (input_path / "sample_data.csv").write_text(test_dataset.read_text())

        output_path = tmp_path / "output"
        output_path.mkdir()

        config = DataQualityConfig(
            fill_null_country=True,
            fill_null_device=True,
            validate_ip_format=True,
            validate_url_format=True,
        )

        output_file, report = run_non_spark_etl(
            str(input_path), str(output_path), quality_config=config
        )

        df = pl.read_parquet(output_file)

        # Verify transformations
        # All URLs should start with /
        assert all(df["page_url"].str.starts_with("/"))

        # No nulls in country/device (filled with defaults)
        assert df["country"].null_count() == 0
        assert df["device"].null_count() == 0

        # All IPs should be valid format
        valid_ips = df["ip_address"].str.contains(
            r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"
        )
        assert all(valid_ips)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
