#!/usr/bin/env python3
"""CLI script to generate clickstream data for ETL benchmarking."""

import argparse
import logging
import sys
from pathlib import Path

from src.data_generation.generator import generate_benchmark_data

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Parse CLI arguments and generate clickstream data.

    Parse arguments and generate data accordingly.
    """
    parser = argparse.ArgumentParser(
        description="Generate clickstream data for ETL benchmarking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_data.py small
  python generate_data.py medium --output data/benchmark --days 14
  python generate_data.py large --formats parquet --seed 123
        """,
    )

    parser.add_argument(
        "size",
        choices=["small", "medium", "large"],
        help="""Data size: small (~100K records), medium (~10M records),
        large (~100M records)""",
    )

    parser.add_argument(
        "--output",
        "-o",
        default="data/generated",
        help="Output directory (default: data/generated)",
    )

    parser.add_argument(
        "--formats",
        "-f",
        nargs="+",
        choices=["csv", "parquet"],
        default=["csv", "parquet"],
        help="Output formats (default: csv parquet)",
    )

    parser.add_argument(
        "--days",
        "-d",
        type=int,
        default=7,
        help="Number of incremental daily files (default: 7)",
    )

    parser.add_argument(
        "--seed",
        "-s",
        type=int,
        help="Random seed for reproducible generation",
    )

    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress output messages",
    )

    args = parser.parse_args()
    if args.quiet:
        logger.setLevel(logging.WARNING)

    logger.info(f"🚀 Generating {args.size} clickstream dataset...")
    logger.info(f"   Output: {args.output}")
    logger.info(f"   Formats: {', '.join(args.formats)}")
    logger.info(f"   Incremental days: {args.days}")
    if args.seed:
        logger.info(f"   Seed: {args.seed}")
    logger.info("")

    try:
        result = generate_benchmark_data(
            size=args.size,
            output_dir=args.output,
            formats=args.formats,
            seed=args.seed,
            incremental_days=args.days,
        )
        logger.info("✅ Generation complete!")
        logger.info(f"   Bulk records: {result['bulk_record_count']:,}")
        logger.info(f"   Incremental files: {result['incremental_days']} days")
        logger.info("")

        # Show file sizes
        for format_type, files in result["files"].items():
            bulk_size = files["bulk"]["size_mb"]
            total_incremental_size = sum(f["size_mb"] for f in files["incremental"])
            logger.info(f"   {format_type.upper()} files:")
            logger.info(f"     Bulk: {bulk_size:.1f} MB")
            logger.info(f"     Incremental: {total_incremental_size:.1f} MB")

        logger.info(f"\n📁 Files saved to: {Path(args.output).absolute()}")

    except Exception:
        logger.exception("❌ Error occurred during data generation")
        sys.exit(1)


if __name__ == "__main__":
    main()
