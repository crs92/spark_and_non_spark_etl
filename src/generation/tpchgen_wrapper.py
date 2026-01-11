#!/usr/bin/env python3
# ruff: noqa: S603
"""Wrapper for tpchgen-rs CLI tool.

This module provides a Python interface to the tpchgen-rs Rust tool,
which is 20x faster than DuckDB's dbgen and uses constant memory.

tpchgen-rs generates TPC-H data directly to Parquet files with streaming,
making it ideal for generating large datasets on memory-constrained systems.

Installation:
    cargo install tpchgen-cli

Reference:
    https://github.com/clflushopt/tpchgen-rs
    https://datafusion.apache.org/blog/2025/04/10/fastest-tpch-generator/

Note:
    S603 (subprocess security check) is disabled for this file because we're
    calling trusted CLI tools (tpchgen-cli and aws) with controlled arguments.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import ClassVar

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class TPCHGenWrapper:
    """Wrapper for tpchgen-rs CLI tool.

    This class provides a Python interface to tpchgen-rs, handling:
    - Local Parquet generation
    - S3 upload
    - Progress logging
    - Error handling

    Attributes:
        scale_factor: TPC-H scale factor (10 = ~10GB, 100 = ~100GB)
        s3_bucket: Target S3 bucket name
        s3_prefix: S3 prefix for TPC-H data
        output_format: Output format (parquet, csv, tbl)
        num_threads: Number of threads for parallel generation
    """

    # TPC-H table names
    TPCH_TABLES: ClassVar[list[str]] = [
        "customer",
        "lineitem",
        "nation",
        "orders",
        "part",
        "partsupp",
        "region",
        "supplier",
    ]

    def __init__(
        self,
        scale_factor: int,
        s3_bucket: str,
        s3_prefix: str,
        output_format: str = "parquet",
        num_threads: int | None = None,
    ):
        """Initialize TPCHGenWrapper.

        Args:
            scale_factor: TPC-H scale factor (10 = ~10GB, 100 = ~100GB)
            s3_bucket: Target S3 bucket name
            s3_prefix: S3 prefix for TPC-H data (e.g., 'tpch-sf10')
            output_format: Output format (parquet, csv, tbl)
            num_threads: Number of threads (default: all available cores)

        Raises:
            ValueError: If scale_factor is not a positive integer
            RuntimeError: If tpchgen-cli is not installed
        """
        if not isinstance(scale_factor, int) or scale_factor <= 0:
            msg = f"Scale factor must be a positive integer, got: {scale_factor}"
            raise ValueError(msg)

        self.scale_factor = scale_factor
        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix.rstrip("/")
        self.output_format = output_format
        self.num_threads = num_threads

        # Check if tpchgen-cli is installed
        if not self._check_tpchgen_installed():
            msg = (
                "tpchgen-cli is not installed. Install it with:\n"
                "  cargo install tpchgen-cli\n"
                "Or install Rust first: https://rustup.rs/"
            )
            raise RuntimeError(msg)

        logger.info(
            f"Initialized TPCHGenWrapper with scale_factor={scale_factor}, "
            f"s3_bucket={s3_bucket}, s3_prefix={s3_prefix}, "
            f"format={output_format}, threads={num_threads or 'auto'}"
        )

    def _check_tpchgen_installed(self) -> bool:
        """Check if tpchgen-cli is installed.

        Returns:
            True if tpchgen-cli is available, False otherwise
        """
        return shutil.which("tpchgen-cli") is not None

    def generate_and_upload(self, temp_dir: str | None = None) -> None:
        """Generate TPC-H data locally and upload to S3.

        This method:
        1. Generates TPC-H data to a local directory using tpchgen-rs
        2. Uploads the generated files to S3
        3. Cleans up local files

        Args:
            temp_dir: Temporary directory for generation (default: system temp)

        Raises:
            RuntimeError: If generation or upload fails
        """
        # Create temporary directory
        if temp_dir:
            output_dir = Path(temp_dir) / f"tpch-sf{self.scale_factor}"
            output_dir.mkdir(parents=True, exist_ok=True)
            cleanup = False
        else:
            temp_dir_obj = tempfile.mkdtemp(prefix=f"tpch-sf{self.scale_factor}-")
            output_dir = Path(temp_dir_obj)
            cleanup = True

        try:
            logger.info(f"Generating TPC-H data to: {output_dir}")

            # Generate data using tpchgen-cli
            import time

            gen_start = time.time()
            self._run_tpchgen(output_dir)
            gen_time = time.time() - gen_start
            logger.info(f"Generation completed in {gen_time:.2f} seconds")

            # Upload to S3
            upload_start = time.time()
            self._upload_to_s3(output_dir)
            upload_time = time.time() - upload_start
            logger.info(f"S3 upload completed in {upload_time:.2f} seconds")

            logger.info(
                f"Total time: {gen_time + upload_time:.2f} seconds "
                f"(generation: {gen_time:.2f}s, upload: {upload_time:.2f}s)"
            )

        finally:
            # Clean up temporary directory
            if cleanup and output_dir.exists():
                logger.info(f"Cleaning up temporary directory: {output_dir}")
                shutil.rmtree(output_dir)

    def _run_tpchgen(self, output_dir: Path) -> None:
        """Run tpchgen-cli to generate TPC-H data.

        Args:
            output_dir: Directory to write generated files

        Raises:
            RuntimeError: If tpchgen-cli fails
        """
        logger.info(
            f"Running tpchgen-cli for SF {self.scale_factor} "
            f"(format: {self.output_format})"
        )

        # Build command
        cmd = [
            "tpchgen-cli",
            "-s",
            str(self.scale_factor),
            "--format",
            self.output_format,
            "--output-dir",
            str(output_dir),
        ]

        if self.num_threads:
            cmd.extend(["--num-threads", str(self.num_threads)])

        logger.debug(f"Running command: {' '.join(cmd)}")

        try:
            # Run tpchgen-cli
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
            )

            # Log output
            if result.stdout:
                logger.debug(f"tpchgen-cli output:\n{result.stdout}")

            logger.info(f"Successfully generated TPC-H data (SF={self.scale_factor})")

        except subprocess.CalledProcessError as e:
            logger.error(f"tpchgen-cli failed with exit code {e.returncode}")
            logger.error(f"stdout: {e.stdout}")
            logger.error(f"stderr: {e.stderr}")
            raise RuntimeError(f"tpchgen-cli failed: {e.stderr}") from e

    def _upload_to_s3(self, output_dir: Path) -> None:
        """Upload generated files to S3.

        Args:
            output_dir: Directory containing generated files

        Raises:
            RuntimeError: If S3 upload fails
        """
        logger.info(f"Uploading data to s3://{self.s3_bucket}/{self.s3_prefix}")

        # Get AWS region
        aws_region = os.getenv("AWS_REGION", "us-east-1")

        # Build aws s3 sync command
        cmd = [
            "aws",
            "s3",
            "sync",
            str(output_dir),
            f"s3://{self.s3_bucket}/{self.s3_prefix}",
            "--region",
            aws_region,
        ]

        logger.debug(f"Running command: {' '.join(cmd)}")

        try:
            # Run aws s3 sync
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
            )

            # Log output
            if result.stdout:
                logger.info(f"S3 upload output:\n{result.stdout}")

            logger.info(
                f"Successfully uploaded data to s3://{self.s3_bucket}/{self.s3_prefix}"
            )

        except subprocess.CalledProcessError as e:
            logger.error(f"S3 upload failed with exit code {e.returncode}")
            logger.error(f"stdout: {e.stdout}")
            logger.error(f"stderr: {e.stderr}")
            raise RuntimeError(f"S3 upload failed: {e.stderr}") from e

    def list_generated_files(self, output_dir: Path) -> list[str]:
        """List all generated files in the output directory.

        Args:
            output_dir: Directory containing generated files

        Returns:
            List of file paths relative to output_dir
        """
        files = []
        for table_dir in output_dir.iterdir():
            if table_dir.is_dir():
                for file in table_dir.rglob("*"):
                    if file.is_file():
                        files.append(str(file.relative_to(output_dir)))
        return sorted(files)
