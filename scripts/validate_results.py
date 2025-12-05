#!/usr/bin/env python3
"""Results validation script.

This script validates that Polars and Spark implementations produce identical
results, checking data quality, record counts, and aggregation accuracy.

Usage:
    python scripts/validate_results.py --polars-file results/polars_tiny.parquet --spark-file results/spark_tiny.parquet
    python scripts/validate_results.py --data-size tiny
    python scripts/validate_results.py --benchmark-id 20241205_120000
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation check."""

    check_name: str
    passed: bool
    message: str
    details: dict[str, Any] | None = None


class ResultsValidator:
    """Validates benchmark results for correctness and consistency."""

    def __init__(self, tolerance: float = 0.01):
        """Initialize the validator.

        Args:
            tolerance: Relative tolerance for numeric comparisons (default: 1%)
        """
        self.tolerance = tolerance
        self.validation_results: list[ValidationResult] = []

        logger.info("Results Validator initialized")
        logger.info("Numeric tolerance: %.2f%%", tolerance * 100)

    def validate_files_exist(
        self, polars_file: Path, spark_file: Path
    ) -> ValidationResult:
        """Validate that both result files exist.

        Args:
            polars_file: Path to Polars results
            spark_file: Path to Spark results

        Returns:
            ValidationResult
        """
        logger.info("Checking if result files exist...")

        if not polars_file.exists():
            return ValidationResult(
                check_name="files_exist",
                passed=False,
                message=f"Polars file not found: {polars_file}",
            )

        if not spark_file.exists():
            return ValidationResult(
                check_name="files_exist",
                passed=False,
                message=f"Spark file not found: {spark_file}",
            )

        return ValidationResult(
            check_name="files_exist",
            passed=True,
            message="Both result files exist",
            details={
                "polars_file": str(polars_file),
                "spark_file": str(spark_file),
            },
        )

    def validate_record_counts(
        self, polars_df: pl.DataFrame, spark_df: pl.DataFrame
    ) -> ValidationResult:
        """Validate that both DataFrames have the same number of records.

        Args:
            polars_df: Polars DataFrame
            spark_df: Spark DataFrame (as Polars)

        Returns:
            ValidationResult
        """
        logger.info("Validating record counts...")

        polars_count = len(polars_df)
        spark_count = len(spark_df)

        passed = polars_count == spark_count

        return ValidationResult(
            check_name="record_counts",
            passed=passed,
            message=(
                f"Record counts match: {polars_count}"
                if passed
                else f"Record counts differ: Polars={polars_count}, Spark={spark_count}"
            ),
            details={
                "polars_count": polars_count,
                "spark_count": spark_count,
                "difference": abs(polars_count - spark_count),
            },
        )

    def validate_schema(
        self, polars_df: pl.DataFrame, spark_df: pl.DataFrame
    ) -> ValidationResult:
        """Validate that both DataFrames have compatible schemas.

        Args:
            polars_df: Polars DataFrame
            spark_df: Spark DataFrame (as Polars)

        Returns:
            ValidationResult
        """
        logger.info("Validating schemas...")

        polars_cols = set(polars_df.columns)
        spark_cols = set(spark_df.columns)

        missing_in_spark = polars_cols - spark_cols
        missing_in_polars = spark_cols - polars_cols

        if missing_in_spark or missing_in_polars:
            return ValidationResult(
                check_name="schema",
                passed=False,
                message="Schema mismatch detected",
                details={
                    "missing_in_spark": list(missing_in_spark),
                    "missing_in_polars": list(missing_in_polars),
                    "polars_columns": list(polars_cols),
                    "spark_columns": list(spark_cols),
                },
            )

        # Check data types for common columns
        type_mismatches = []
        for col in polars_cols:
            polars_type = str(polars_df[col].dtype)
            spark_type = str(spark_df[col].dtype)

            # Allow some type flexibility (e.g., Int64 vs Int32)
            if not self._types_compatible(polars_type, spark_type):
                type_mismatches.append({
                    "column": col,
                    "polars_type": polars_type,
                    "spark_type": spark_type,
                })

        if type_mismatches:
            return ValidationResult(
                check_name="schema",
                passed=False,
                message=f"Type mismatches found in {len(type_mismatches)} columns",
                details={"type_mismatches": type_mismatches},
            )

        return ValidationResult(
            check_name="schema",
            passed=True,
            message="Schemas are compatible",
            details={
                "columns": list(polars_cols),
                "column_count": len(polars_cols),
            },
        )

    def validate_aggregations(
        self, polars_df: pl.DataFrame, spark_df: pl.DataFrame
    ) -> ValidationResult:
        """Validate that aggregation results match within tolerance.

        Args:
            polars_df: Polars DataFrame
            spark_df: Spark DataFrame (as Polars)

        Returns:
            ValidationResult
        """
        logger.info("Validating aggregation results...")

        # Sort both DataFrames by the same columns for comparison
        sort_cols = ["pickup_location_id", "date"]

        # Check if sort columns exist
        if not all(col in polars_df.columns for col in sort_cols):
            return ValidationResult(
                check_name="aggregations",
                passed=False,
                message="Required columns for sorting not found",
                details={"required_columns": sort_cols},
            )

        polars_sorted = polars_df.sort(sort_cols)
        spark_sorted = spark_df.sort(sort_cols)

        # Compare numeric columns
        numeric_cols = [
            col
            for col in polars_df.columns
            if polars_df[col].dtype in [pl.Float64, pl.Float32, pl.Int64, pl.Int32]
        ]

        mismatches = []

        for col in numeric_cols:
            if col not in spark_df.columns:
                continue

            polars_values = polars_sorted[col].to_numpy()
            spark_values = spark_sorted[col].to_numpy()

            # Calculate relative differences
            differences = []
            for i, (p_val, s_val) in enumerate(zip(polars_values, spark_values)):
                if p_val is None or s_val is None:
                    if p_val != s_val:
                        differences.append({
                            "row": i,
                            "polars": p_val,
                            "spark": s_val,
                            "diff": "null_mismatch",
                        })
                    continue

                # Skip if both are zero
                if p_val == 0 and s_val == 0:
                    continue

                # Calculate relative difference
                rel_diff = abs((p_val - s_val) / p_val) if p_val != 0 else abs(s_val)

                if rel_diff > self.tolerance:
                    differences.append({
                        "row": i,
                        "polars": float(p_val),
                        "spark": float(s_val),
                        "rel_diff": float(rel_diff),
                    })

            if differences:
                mismatches.append({
                    "column": col,
                    "mismatch_count": len(differences),
                    "sample_mismatches": differences[:5],  # First 5 mismatches
                })

        if mismatches:
            return ValidationResult(
                check_name="aggregations",
                passed=False,
                message=f"Aggregation mismatches found in {len(mismatches)} columns",
                details={"mismatches": mismatches},
            )

        return ValidationResult(
            check_name="aggregations",
            passed=True,
            message=f"All aggregations match within {self.tolerance * 100}% tolerance",
            details={
                "numeric_columns_checked": len(numeric_cols),
                "tolerance": self.tolerance,
            },
        )

    def validate_data_quality(self, df: pl.DataFrame, name: str) -> ValidationResult:
        """Validate data quality of a DataFrame.

        Args:
            df: DataFrame to validate
            name: Name of the DataFrame (for reporting)

        Returns:
            ValidationResult
        """
        logger.info("Validating data quality for %s...", name)

        issues = []

        # Check for null values in key columns
        key_columns = ["pickup_location_id", "date", "trip_count"]
        for col in key_columns:
            if col in df.columns:
                null_count = df[col].null_count()
                if null_count > 0:
                    issues.append({
                        "type": "null_values",
                        "column": col,
                        "count": null_count,
                    })

        # Check for negative values in numeric columns
        numeric_cols = [
            col
            for col in df.columns
            if df[col].dtype in [pl.Float64, pl.Float32, pl.Int64, pl.Int32]
        ]

        for col in numeric_cols:
            if col in ["avg_fare", "avg_distance", "avg_price_per_mile", "trip_count"]:
                negative_count = (df[col] < 0).sum()
                if negative_count > 0:
                    issues.append({
                        "type": "negative_values",
                        "column": col,
                        "count": negative_count,
                    })

        # Check for extreme outliers
        for col in ["avg_fare", "avg_price_per_mile"]:
            if col in df.columns:
                max_val = df[col].max()
                if max_val and max_val > 1000:  # Unreasonably high values
                    issues.append({
                        "type": "extreme_outlier",
                        "column": col,
                        "max_value": float(max_val),
                    })

        if issues:
            return ValidationResult(
                check_name=f"data_quality_{name}",
                passed=False,
                message=f"Data quality issues found in {name}",
                details={"issues": issues},
            )

        return ValidationResult(
            check_name=f"data_quality_{name}",
            passed=True,
            message=f"Data quality checks passed for {name}",
            details={
                "record_count": len(df),
                "column_count": len(df.columns),
            },
        )

    def _types_compatible(self, type1: str, type2: str) -> bool:
        """Check if two data types are compatible.

        Args:
            type1: First type
            type2: Second type

        Returns:
            True if types are compatible
        """
        # Exact match
        if type1 == type2:
            return True

        # Integer types are compatible
        int_types = [
            "Int8",
            "Int16",
            "Int32",
            "Int64",
            "UInt8",
            "UInt16",
            "UInt32",
            "UInt64",
        ]
        if any(t in type1 for t in int_types) and any(t in type2 for t in int_types):
            return True

        # Float types are compatible
        float_types = ["Float32", "Float64"]
        if any(t in type1 for t in float_types) and any(
            t in type2 for t in float_types
        ):
            return True

        # Date types are compatible
        date_types = ["Date", "Datetime"]
        if any(t in type1 for t in date_types) and any(t in type2 for t in date_types):
            return True

        return False

    def validate_all(
        self, polars_file: Path, spark_file: Path
    ) -> list[ValidationResult]:
        """Run all validation checks.

        Args:
            polars_file: Path to Polars results
            spark_file: Path to Spark results

        Returns:
            List of ValidationResult objects
        """
        logger.info("=" * 60)
        logger.info("Starting Results Validation")
        logger.info("=" * 60)
        logger.info("Polars file: %s", polars_file)
        logger.info("Spark file: %s", spark_file)
        logger.info("=" * 60)

        self.validation_results = []

        # Check files exist
        result = self.validate_files_exist(polars_file, spark_file)
        self.validation_results.append(result)

        if not result.passed:
            logger.error("Files not found, cannot continue validation")
            return self.validation_results

        # Load DataFrames
        def _raise_no_parquet_files(path: Path) -> None:
            """Raise FileNotFoundError for missing parquet files."""
            raise FileNotFoundError(f"No parquet files in {path}")

        try:
            logger.info("Loading Polars results...")
            polars_df = pl.read_parquet(polars_file)
            logger.info("Loaded %d records", len(polars_df))

            logger.info("Loading Spark results...")
            # Spark writes to a directory, find the parquet file
            if spark_file.is_dir():
                parquet_files = list(spark_file.glob("*.parquet"))
                if not parquet_files:
                    _raise_no_parquet_files(spark_file)
                spark_file = parquet_files[0]

            spark_df = pl.read_parquet(spark_file)
            logger.info("Loaded %d records", len(spark_df))

        except Exception as e:
            logger.error("Failed to load results: %s", e)
            self.validation_results.append(
                ValidationResult(
                    check_name="load_files",
                    passed=False,
                    message=f"Failed to load files: {e}",
                )
            )
            return self.validation_results

        # Run validation checks
        self.validation_results.append(self.validate_record_counts(polars_df, spark_df))
        self.validation_results.append(self.validate_schema(polars_df, spark_df))
        self.validation_results.append(self.validate_data_quality(polars_df, "polars"))
        self.validation_results.append(self.validate_data_quality(spark_df, "spark"))
        self.validation_results.append(self.validate_aggregations(polars_df, spark_df))

        return self.validation_results

    def print_summary(self):
        """Print a summary of validation results."""
        logger.info("\n" + "=" * 60)
        logger.info("Validation Summary")
        logger.info("=" * 60)

        passed = sum(1 for r in self.validation_results if r.passed)
        failed = len(self.validation_results) - passed

        logger.info("Total Checks: %d", len(self.validation_results))
        logger.info("Passed: %d", passed)
        logger.info("Failed: %d", failed)
        logger.info("")

        for result in self.validation_results:
            status = "✓" if result.passed else "✗"
            logger.info("%s %s: %s", status, result.check_name, result.message)

            if not result.passed and result.details:
                logger.info("  Details: %s", json.dumps(result.details, indent=4))

        logger.info("=" * 60)

        if failed == 0:
            logger.info("✓ All validation checks passed!")
        else:
            logger.error("✗ %d validation check(s) failed", failed)

    def save_results(self, output_file: str) -> str:
        """Save validation results to a JSON file.

        Args:
            output_file: Path to output file

        Returns:
            Path to saved file
        """
        data = {
            "timestamp": pl.datetime("now").strftime("%Y-%m-%d %H:%M:%S"),
            "tolerance": self.tolerance,
            "total_checks": len(self.validation_results),
            "passed": sum(1 for r in self.validation_results if r.passed),
            "failed": sum(1 for r in self.validation_results if not r.passed),
            "results": [
                {
                    "check_name": r.check_name,
                    "passed": r.passed,
                    "message": r.message,
                    "details": r.details,
                }
                for r in self.validation_results
            ],
        }

        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)

        logger.info("Validation results saved to: %s", output_file)
        return output_file


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validate benchmark results for correctness"
    )
    parser.add_argument(
        "--polars-file",
        type=str,
        help="Path to Polars results file",
    )
    parser.add_argument(
        "--spark-file",
        type=str,
        help="Path to Spark results file or directory",
    )
    parser.add_argument(
        "--data-size",
        type=str,
        help="Data size to validate (auto-finds latest results)",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.01,
        help="Relative tolerance for numeric comparisons (default: 0.01 = 1%%)",
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default="benchmark_results",
        help="Directory containing results (default: benchmark_results)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file for validation results (default: auto-generated)",
    )

    args = parser.parse_args()

    # Determine file paths
    if args.polars_file and args.spark_file:
        polars_file = Path(args.polars_file)
        spark_file = Path(args.spark_file)
    elif args.data_size:
        results_dir = Path(args.results_dir)

        # Find latest Polars results
        polars_pattern = f"polars_*_{args.data_size}_*.parquet"
        polars_files = list(results_dir.glob(polars_pattern))

        if not polars_files:
            logger.error("No Polars results found for data size: %s", args.data_size)
            sys.exit(1)

        polars_file = max(polars_files, key=lambda p: p.stat().st_mtime)

        # Find latest Spark results
        spark_pattern = f"spark_*_{args.data_size}_*"
        spark_dirs = [p for p in results_dir.glob(spark_pattern) if p.is_dir()]

        if not spark_dirs:
            logger.error("No Spark results found for data size: %s", args.data_size)
            sys.exit(1)

        spark_file = max(spark_dirs, key=lambda p: p.stat().st_mtime)

        logger.info("Auto-detected files:")
        logger.info("  Polars: %s", polars_file)
        logger.info("  Spark: %s", spark_file)
    else:
        logger.error(
            "Must specify either --polars-file and --spark-file, or --data-size"
        )
        sys.exit(1)

    # Create validator
    validator = ResultsValidator(tolerance=args.tolerance)

    try:
        # Run validation
        validator.validate_all(polars_file, spark_file)

        # Print summary
        validator.print_summary()

        # Save results
        if args.output:
            output_file = args.output
        else:
            timestamp = pl.datetime("now").strftime("%Y%m%d_%H%M%S")
            output_file = f"{args.results_dir}/validation_results_{timestamp}.json"

        validator.save_results(output_file)

        # Exit with appropriate code
        failed = sum(1 for r in validator.validation_results if not r.passed)
        sys.exit(1 if failed > 0 else 0)

    except Exception as e:
        logger.error("Validation failed: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
