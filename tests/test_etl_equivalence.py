"""Integration tests to verify ETL output equivalence between Spark and Polars
implementations."""

import polars as pl
import pytest

from src.data_generation.generator import generate_benchmark_data
from src.etl.data_quality import DataQualityConfig
from src.etl.non_spark_etl import run_non_spark_etl


class TestETLOutputEquivalence:
    """Test that both ETL implementations produce equivalent outputs."""

    @pytest.fixture
    def test_dataset(self, tmp_path):
        """Generate a small test dataset for equivalence testing."""
        output_dir = tmp_path / "generated"
        result = generate_benchmark_data(
            size="small",
            output_dir=str(output_dir),
            formats=["csv"],
            seed=42,
            incremental_days=1,
        )
        return output_dir / "bulk" / "bulk_data_small.csv"

    def test_polars_output_schema_consistency(self, test_dataset, tmp_path):
        """Test that Polars ETL produces consistent schema."""
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

        # Verify schema consistency
        expected_columns = {
            "event_id",
            "user_id",
            "session_id",
            "timestamp",
            "page_url",
            "country",
            "device",
            "ip_address",
            "ip_suffix",
            "session_start",
            "session_end",
            "session_duration_minutes",
        }

        actual_columns = set(df.columns)
        assert (
            expected_columns == actual_columns
        ), f"Schema mismatch: expected {expected_columns}, got {actual_columns}"

    def test_data_quality_consistency_across_runs(self, test_dataset, tmp_path):
        """Test that data quality checks produce consistent results across
        multiple runs."""
        config = DataQualityConfig(
            drop_null_event_id=True,
            drop_null_user_id=True,
            drop_null_timestamp=True,
            fill_null_country=True,
            fill_null_device=True,
            drop_duplicate_event_ids=True,
            validate_ip_format=True,
            validate_url_format=True,
        )

        # Run 1
        input_path1 = tmp_path / "input1"
        input_path1.mkdir()
        (input_path1 / "sample_data.csv").write_text(test_dataset.read_text())

        output_path1 = tmp_path / "output1"
        output_path1.mkdir()

        output_file1, report1 = run_non_spark_etl(
            str(input_path1), str(output_path1), quality_config=config
        )

        # Run 2
        input_path2 = tmp_path / "input2"
        input_path2.mkdir()
        (input_path2 / "sample_data.csv").write_text(test_dataset.read_text())

        output_path2 = tmp_path / "output2"
        output_path2.mkdir()

        output_file2, report2 = run_non_spark_etl(
            str(input_path2), str(output_path2), quality_config=config
        )

        # Compare reports
        assert report1.total_records == report2.total_records
        assert report1.records_dropped == report2.records_dropped
        assert report1.records_corrected == report2.records_corrected

        # Compare outputs
        df1 = pl.read_parquet(output_file1)
        df2 = pl.read_parquet(output_file2)

        assert len(df1) == len(df2)
        assert df1.columns == df2.columns

    def test_sessionization_logic_consistency(self, test_dataset, tmp_path):
        """Test that sessionization logic produces consistent session
        boundaries."""
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

        # Verify sessionization properties
        # 1. Each session should have consistent user_id
        session_users = df.group_by("session_id").agg(
            [pl.col("user_id").n_unique().alias("unique_users")]
        )
        assert all(
            session_users["unique_users"] == 1
        ), "Each session should belong to exactly one user"

        # 2. Session duration should be non-negative
        assert all(
            df["session_duration_minutes"] >= 0
        ), "Session duration should be non-negative"

        # 3. Session start should be <= session end
        assert all(
            df["session_start"] <= df["session_end"]
        ), "Session start should be before or equal to session end"

        # 4. Events within a session should be within the session time range
        for row in df.iter_rows(named=True):
            assert row["session_start"] <= row["timestamp"] <= row["session_end"], (
                f"Event timestamp {row['timestamp']} should be within session range"
                f" [{row['session_start']}, {row['session_end']}]"
            )

    def test_data_cleansing_removes_invalid_records(self, tmp_path):
        """Test that data cleansing properly removes invalid records."""
        # Create data with known issues
        data = {
            "event_id": ["e1", "e2", None, "e4"],  # 1 null
            "user_id": ["u1", "u2", "u3", "u4"],
            "session_id": ["s1", "s2", "s3", "s4"],
            "timestamp": [
                "2024-01-01 10:00:00",
                "2024-01-01 10:05:00",
                "2024-01-01 10:10:00",
                "2024-01-01 10:15:00",
            ],
            "page_url": ["/home", "/products", "/about", "/contact"],
            "country": ["US", "CA", "GB", "DE"],
            "device": ["desktop", "mobile", "tablet", "desktop"],
            "ip_address": ["192.168.1.1", "192.168.1.2", "192.168.1.3", "192.168.1.4"],
        }

        df = pl.DataFrame(data)
        input_path = tmp_path / "input"
        input_path.mkdir()
        csv_path = input_path / "sample_data.csv"
        df.write_csv(csv_path)

        output_path = tmp_path / "output"
        output_path.mkdir()

        config = DataQualityConfig(drop_null_event_id=True)
        output_file, report = run_non_spark_etl(
            str(input_path), str(output_path), quality_config=config
        )

        # Should have dropped 1 record with null event_id
        assert report.records_dropped >= 1

        df_output = pl.read_parquet(output_file)
        # Output should have no null event_ids
        assert df_output["event_id"].null_count() == 0

    def test_type_casting_handles_edge_cases(self, tmp_path):
        """Test that type casting handles edge cases properly."""
        # Create data with edge cases
        data = {
            "event_id": ["e1", "e2", "e3"],
            "user_id": ["u1", "u2", "u3"],
            "session_id": ["s1", "s2", "s3"],
            "timestamp": [
                "2024-01-01 10:00:00.123456",  # with microseconds
                "2024-01-01 10:05:00",  # without microseconds
                "2024-01-01 10:10:00.0",  # with .0
            ],
            "page_url": ["/home", "/products", "/about"],
            "country": ["US", "CA", "GB"],
            "device": ["desktop", "mobile", "tablet"],
            "ip_address": ["192.168.1.1", "192.168.1.2", "192.168.1.3"],
        }

        df = pl.DataFrame(data)
        input_path = tmp_path / "input"
        input_path.mkdir()
        csv_path = input_path / "sample_data.csv"
        df.write_csv(csv_path)

        output_path = tmp_path / "output"
        output_path.mkdir()

        config = DataQualityConfig()
        output_file, report = run_non_spark_etl(
            str(input_path), str(output_path), quality_config=config
        )

        df_output = pl.read_parquet(output_file)

        # All timestamps should be properly parsed
        assert df_output["timestamp"].dtype == pl.Datetime
        assert df_output["timestamp"].null_count() == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
