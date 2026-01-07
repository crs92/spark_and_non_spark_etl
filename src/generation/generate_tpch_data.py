#!/usr/bin/env python3
"""CLI script for generating TPC-H benchmark data.

This script provides a command-line interface for generating TPC-H data
at various scale factors and writing it to S3.

Usage:
    python -m src.generation.generate_tpch_data --scale-factor 10
    python -m src.generation.generate_tpch_data --scale-factor 100 --bucket my-bucket
"""

import argparse
import os
import sys
import time

from src.generation.tpch_generator import TPCHGenerator
from src.utils.logging_config import get_logger, log_environment_info

logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Generate TPC-H benchmark data and write to S3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate SF 10 data (~10GB) using environment variables
  python -m src.generation.generate_tpch_data --scale-factor 10

  # Generate SF 100 data (~100GB) with explicit bucket
  python -m src.generation.generate_tpch_data --scale-factor 100 --bucket my-bucket

  # Generate specific table only
  python -m src.generation.generate_tpch_data --scale-factor 10 --table lineitem

Environment Variables:
  S3_BUCKET_NAME: S3 bucket for TPC-H data (required if --bucket not provided)
  AWS_REGION: AWS region (default: us-east-1)
  PARQUET_COMPRESSION: Compression codec (default: snappy)
  DEBUG: Enable debug logging (true/false)
        """,
    )

    parser.add_argument(
        "--scale-factor",
        type=int,
        required=True,
        help="TPC-H scale factor (10 = ~10GB, 100 = ~100GB)",
    )

    parser.add_argument(
        "--bucket",
        type=str,
        help="S3 bucket name (overrides S3_BUCKET_NAME env var)",
    )

    parser.add_argument(
        "--prefix",
        type=str,
        help="S3 prefix for data (default: tpch-sf{scale_factor})",
    )

    parser.add_argument(
        "--table",
        type=str,
        choices=TPCHGenerator.TPCH_TABLES,
        help="Generate only a specific table (default: all tables)",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    return parser.parse_args()


def validate_environment() -> None:
    """Validate required environment variables.

    Raises:
        SystemExit: If required environment variables are missing
    """
    required_vars = []

    # Check for S3 bucket (can be provided via CLI or env var)
    if not os.getenv("S3_BUCKET_NAME"):
        required_vars.append("S3_BUCKET_NAME")

    if required_vars:
        logger.error("Missing required environment variables:")
        for var in required_vars:
            logger.error(f"  - {var}")
        logger.error("\nPlease set these variables or provide them via CLI arguments")
        sys.exit(1)


def main() -> None:
    """Main entry point for TPC-H data generation."""
    args = parse_args()

    # Set up logging
    if args.verbose:
        os.environ["DEBUG"] = "true"

    logger.info("=" * 80)
    logger.info("TPC-H Data Generation")
    logger.info("=" * 80)

    # Log environment info
    log_environment_info(logger)

    # Get S3 bucket from args or environment
    s3_bucket = args.bucket or os.getenv("S3_BUCKET_NAME")
    if not s3_bucket:
        logger.error(
            "S3 bucket must be provided via --bucket or S3_BUCKET_NAME env var"
        )
        sys.exit(1)

    # Determine S3 prefix
    s3_prefix = args.prefix if args.prefix else f"tpch-sf{args.scale_factor}"

    logger.info("Configuration:")
    logger.info(f"  Scale Factor: {args.scale_factor}")
    logger.info(f"  S3 Bucket: {s3_bucket}")
    logger.info(f"  S3 Prefix: {s3_prefix}")
    logger.info(f"  Target Table: {args.table or 'all tables'}")
    logger.info("")

    # Create generator
    try:
        start_time = time.time()

        with TPCHGenerator(args.scale_factor, s3_bucket, s3_prefix) as generator:
            if args.table:
                # Generate single table
                logger.info(f"Generating single table: {args.table}")

                # Check if lineitem needs partitioning
                partition_by = "l_shipdate" if args.table == "lineitem" else None
                generator.generate_table(args.table, partition_by)

            else:
                # Generate all tables
                logger.info("Generating all TPC-H tables")
                generator.generate_all_tables()

        elapsed_time = time.time() - start_time
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"Generation completed successfully in {elapsed_time:.2f} seconds")
        logger.info(f"Data location: s3://{s3_bucket}/{s3_prefix}")
        logger.info("=" * 80)

    except ValueError as e:
        logger.error(f"Invalid configuration: {e}")
        sys.exit(1)

    except RuntimeError as e:
        logger.error(f"Generation failed: {e}")
        sys.exit(1)

    except KeyboardInterrupt:
        logger.warning("Generation interrupted by user")
        sys.exit(130)

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
