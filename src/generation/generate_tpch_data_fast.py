#!/usr/bin/env python3
"""CLI script for generating TPC-H benchmark data using tpchgen-rs.

This script uses tpchgen-rs (Rust-based generator) which is 20x faster
than DuckDB's dbgen and uses constant memory regardless of scale factor.

Performance comparison:
- SF 10: ~6 seconds (vs 30+ minutes with DuckDB)
- SF 100: ~45 seconds (vs hours with DuckDB)
- Memory: Constant ~2GB (vs 10-100GB+ with DuckDB)

Usage:
    python -m src.generation.generate_tpch_data_fast --scale-factor 10
    python -m src.generation.generate_tpch_data_fast --scale-factor 100 --bucket my-bucket
"""

import argparse
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from src.generation.tpchgen_wrapper import TPCHGenWrapper
from src.utils.logging_config import get_logger, log_environment_info

logger = get_logger(__name__)


def load_environment() -> None:
    """Load environment variables from .env file if it exists.

    Searches for .env file in the following order:
    1. Current working directory
    2. Project root directory (where pyproject.toml is located)

    Environment variables already set in the OS take precedence.
    """
    # Try current directory first
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        logger.debug(f"Loading environment from: {env_path}")
        load_dotenv(env_path, override=False)
        return

    # Try project root (look for pyproject.toml)
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            env_path = parent / ".env"
            if env_path.exists():
                logger.debug(f"Loading environment from: {env_path}")
                load_dotenv(env_path, override=False)
                return

    logger.debug("No .env file found, using OS environment variables only")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Generate TPC-H benchmark data using tpchgen-rs (fast!)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate SF 10 data (~10GB) in ~6 seconds
  python -m src.generation.generate_tpch_data_fast --scale-factor 10

  # Generate SF 100 data (~100GB) in ~45 seconds
  python -m src.generation.generate_tpch_data_fast --scale-factor 100 --bucket my-bucket

  # Generate with custom thread count
  python -m src.generation.generate_tpch_data_fast --scale-factor 10 --threads 8

  # Keep local files (don't clean up)
  python -m src.generation.generate_tpch_data_fast --scale-factor 10 --keep-local

Performance:
  tpchgen-rs is 20x faster than DuckDB's dbgen:
  - SF 1: ~1.5 seconds
  - SF 10: ~6 seconds
  - SF 100: ~45 seconds
  - SF 1000: ~10 minutes

  Memory usage is constant (~2GB) regardless of scale factor!

Configuration:
  The script loads configuration from .env file (if present) or environment variables.
  CLI arguments override .env file values, which override OS environment variables.

  Priority order: CLI args > .env file > OS environment

Environment Variables (.env file or OS):
  S3_BUCKET_NAME: S3 bucket for TPC-H data (required if --bucket not provided)
  AWS_REGION: AWS region (default: us-east-1)
  AWS_ACCESS_KEY_ID: AWS access key (optional, uses IAM role if not set)
  AWS_SECRET_ACCESS_KEY: AWS secret key (optional, uses IAM role if not set)
  DEBUG: Enable debug logging (true/false)
  LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR)

Prerequisites:
  tpchgen-cli must be installed:
    cargo install tpchgen-cli

  If you don't have Rust/Cargo:
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
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
        "--format",
        type=str,
        choices=["parquet", "csv", "tbl"],
        default="parquet",
        help="Output format (default: parquet)",
    )

    parser.add_argument(
        "--threads",
        type=int,
        help="Number of threads for parallel generation (default: all cores)",
    )

    parser.add_argument(
        "--temp-dir",
        type=str,
        help="Temporary directory for generation (default: system temp)",
    )

    parser.add_argument(
        "--keep-local",
        action="store_true",
        help="Keep local files after upload (requires --temp-dir)",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point for TPC-H data generation."""
    # Load .env file first (before parsing args, so DEBUG can be set)
    load_environment()

    args = parse_args()

    # Set up logging
    if args.verbose:
        os.environ["DEBUG"] = "true"

    logger.info("=" * 80)
    logger.info("TPC-H Data Generation (using tpchgen-rs)")
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

    # Validate --keep-local requires --temp-dir
    if args.keep_local and not args.temp_dir:
        logger.error("--keep-local requires --temp-dir to be specified")
        sys.exit(1)

    logger.info("Configuration:")
    logger.info(f"  Scale Factor: {args.scale_factor}")
    logger.info(f"  S3 Bucket: {s3_bucket}")
    logger.info(f"  S3 Prefix: {s3_prefix}")
    logger.info(f"  Output Format: {args.format}")
    logger.info(f"  Threads: {args.threads or 'auto (all cores)'}")
    logger.info(f"  Temp Dir: {args.temp_dir or 'system temp'}")
    logger.info(f"  Keep Local: {args.keep_local}")
    logger.info("")

    # Create generator
    try:
        start_time = time.time()

        generator = TPCHGenWrapper(
            scale_factor=args.scale_factor,
            s3_bucket=s3_bucket,
            s3_prefix=s3_prefix,
            output_format=args.format,
            num_threads=args.threads,
        )

        # Generate and upload
        temp_dir = args.temp_dir if args.keep_local else None
        generator.generate_and_upload(temp_dir=temp_dir)

        elapsed_time = time.time() - start_time
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"Generation completed successfully in {elapsed_time:.2f} seconds")
        logger.info(f"Data location: s3://{s3_bucket}/{s3_prefix}")
        if args.keep_local and args.temp_dir:
            logger.info(f"Local files: {args.temp_dir}/tpch-sf{args.scale_factor}")
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
