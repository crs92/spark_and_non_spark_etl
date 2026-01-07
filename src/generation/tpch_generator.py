"""TPC-H data generator using DuckDB.

This module provides functionality to generate TPC-H benchmark data at
various scale factors and write it to S3 in Parquet format with
appropriate partitioning.
"""

import os
from typing import ClassVar

import duckdb

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class TPCHGenerator:
    """Generates TPC-H benchmark data and writes to S3.

    This class uses DuckDB's built-in TPC-H extension to generate industry-standard
    benchmark data at configurable scale factors. Data is written directly to S3
    in Parquet format with Snappy compression.

    Attributes:
        scale_factor: TPC-H scale factor (10 = ~10GB, 100 = ~100GB)
        s3_bucket: Target S3 bucket name
        s3_prefix: S3 prefix for TPC-H data
        conn: DuckDB connection instance
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

    def __init__(self, scale_factor: int, s3_bucket: str, s3_prefix: str):
        """Initialize TPC-H generator.

        Args:
            scale_factor: TPC-H scale factor (10 = ~10GB, 100 = ~100GB)
            s3_bucket: Target S3 bucket name
            s3_prefix: S3 prefix for TPC-H data (e.g., 'tpch-sf10')

        Raises:
            ValueError: If scale_factor is not a positive integer
        """
        if not isinstance(scale_factor, int) or scale_factor <= 0:
            msg = f"Scale factor must be a positive integer, got: {scale_factor}"
            raise ValueError(msg)

        self.scale_factor = scale_factor
        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix.rstrip("/")
        self.conn: duckdb.DuckDBPyConnection | None = None

        logger.info(
            f"Initialized TPCHGenerator with scale_factor={scale_factor}, "
            f"s3_bucket={s3_bucket}, s3_prefix={s3_prefix}"
        )

    def _setup_duckdb_connection(self) -> duckdb.DuckDBPyConnection:
        """Set up DuckDB connection with required extensions.

        Configures DuckDB with:
        - TPC-H extension for data generation
        - httpfs extension for S3 access
        - AWS credentials from environment

        Returns:
            Configured DuckDB connection

        Raises:
            RuntimeError: If required extensions cannot be loaded
        """
        logger.info("Setting up DuckDB connection with S3 and TPC-H extensions")

        try:
            # Create in-memory DuckDB connection
            conn = duckdb.connect(":memory:")

            # Install and load required extensions
            logger.debug("Installing TPC-H extension")
            conn.execute("INSTALL tpch")
            conn.execute("LOAD tpch")

            logger.debug("Installing httpfs extension for S3 access")
            conn.execute("INSTALL httpfs")
            conn.execute("LOAD httpfs")

            # Configure S3 credentials from environment
            aws_region = os.getenv("AWS_REGION", "eu-central-1")
            logger.debug(f"Configuring S3 access for region: {aws_region}")

            conn.execute(f"SET s3_region='{aws_region}'")

            # Set AWS credentials if provided (otherwise uses IAM role)
            aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
            aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
            aws_session_token = os.getenv("AWS_SESSION_TOKEN")

            if aws_access_key and aws_secret_key:
                logger.debug("Using AWS credentials from environment variables")
                conn.execute(f"SET s3_access_key_id='{aws_access_key}'")
                conn.execute(f"SET s3_secret_access_key='{aws_secret_key}'")

                if aws_session_token:
                    conn.execute(f"SET s3_session_token='{aws_session_token}'")
            else:
                logger.debug("Using IAM role for S3 access")

            return conn

        except Exception as e:
            logger.error(f"Failed to setup DuckDB connection: {e}")
            raise RuntimeError(f"DuckDB setup failed: {e}") from e
        else:
            logger.info("DuckDB connection configured successfully")

    def _generate_tpch_data(self) -> None:
        """Generate TPC-H data at the configured scale factor.

        Uses DuckDB's dbgen function to create all TPC-H tables in memory.

        Raises:
            RuntimeError: If data generation fails
        """
        logger.info(f"Generating TPC-H data at scale factor {self.scale_factor}")

        try:
            # Generate TPC-H data using dbgen
            self.conn.execute(f"CALL dbgen(sf={self.scale_factor})")
            logger.info(f"Successfully generated TPC-H data (SF={self.scale_factor})")

        except Exception as e:
            logger.error(f"Failed to generate TPC-H data: {e}")
            raise RuntimeError(f"TPC-H data generation failed: {e}") from e

    def generate_table(self, table_name: str, partition_by: str | None = None) -> None:
        """Generate and write a single TPC-H table to S3.

        Args:
            table_name: Name of TPC-H table (e.g., 'lineitem', 'orders')
            partition_by: Optional column to partition by (for lineitem: 'l_shipdate')

        Raises:
            ValueError: If table_name is not a valid TPC-H table
            RuntimeError: If table generation or write fails
        """
        if table_name not in self.TPCH_TABLES:
            msg = (
                f"Invalid table name: {table_name}. "
                f"Must be one of: {', '.join(self.TPCH_TABLES)}"
            )
            raise ValueError(msg)

        logger.info(f"Generating table: {table_name}")

        # Ensure connection is established
        if self.conn is None:
            self.conn = self._setup_duckdb_connection()
            self._generate_tpch_data()

        try:
            # Get compression codec from environment
            compression = os.getenv("PARQUET_COMPRESSION", "snappy").lower()
            logger.debug(f"Using Parquet compression: {compression}")

            # Build S3 path
            s3_path = f"s3://{self.s3_bucket}/{self.s3_prefix}/{table_name}"

            if partition_by:
                # Partitioned write (for lineitem table)
                logger.info(f"Writing {table_name} with partitioning by {partition_by}")
                self._write_partitioned_table(table_name, partition_by, s3_path)
            else:
                # Non-partitioned write
                logger.info(f"Writing {table_name} to {s3_path}")

                # Write table to S3 as Parquet
                query = f"""
                    COPY {table_name}
                    TO '{s3_path}'
                    (FORMAT PARQUET, COMPRESSION '{compression}')
                """
                self.conn.execute(query)

            logger.info(f"Successfully wrote {table_name} to S3")

        except Exception as e:
            logger.error(f"Failed to write table {table_name}: {e}")
            raise RuntimeError(f"Table write failed for {table_name}: {e}") from e

    def _write_partitioned_table(
        self, table_name: str, partition_column: str, s3_base_path: str
    ) -> None:
        """Write a table with Hive-style partitioning and zone map
        optimization.

        Extracts year and month from the partition column and creates
        a Hive-style partitioned structure: year=YYYY/month=MM

        The data is sorted by the partition column before writing to enable
        DuckDB's zone map optimization (min/max tracking in metadata), which
        can dramatically improve query performance (30%+ faster scans).

        Reference: https://blog.dataexpert.io/p/i-processed-1-tb-with-duckdb-in-30

        Args:
            table_name: Name of the table to partition
            partition_column: Column to partition by (e.g., 'l_shipdate')
            s3_base_path: Base S3 path for the table

        Raises:
            RuntimeError: If partitioned write fails
        """
        logger.info(
            f"Writing {table_name} with Hive-style partitioning by {partition_column}"
        )
        logger.info(f"Sorting by {partition_column} to enable zone map optimization")

        try:
            # Get compression codec
            compression = os.getenv("PARQUET_COMPRESSION", "snappy").lower()

            # Write with Hive partitioning
            # DuckDB will automatically create year=YYYY/month=MM structure
            # IMPORTANT: ORDER BY enables zone map optimization for faster scans
            query = f"""
                COPY (
                    SELECT
                        *,
                        YEAR({partition_column}) as year,
                        MONTH({partition_column}) as month
                    FROM {table_name}
                    ORDER BY {partition_column}
                )
                TO '{s3_base_path}'
                (FORMAT PARQUET, PARTITION_BY (year, month), COMPRESSION '{compression}')
            """

            self.conn.execute(query)
            logger.info(
                f"Successfully wrote partitioned {table_name} to {s3_base_path} "
                f"(sorted by {partition_column} for zone map optimization)"
            )

        except Exception as e:
            logger.error(f"Failed to write partitioned table {table_name}: {e}")
            raise RuntimeError(f"Partitioned write failed for {table_name}: {e}") from e

    def generate_all_tables(self) -> None:
        """Generate all 8 TPC-H tables and write to S3.

        Tables are generated in the following order:
        1. Small dimension tables (nation, region)
        2. Medium dimension tables (customer, supplier, part)
        3. Large fact tables (partsupp, orders)
        4. Largest fact table with partitioning (lineitem)

        Raises:
            RuntimeError: If any table generation fails
        """
        logger.info("Starting generation of all TPC-H tables")

        # Ensure connection is established and data is generated
        if self.conn is None:
            self.conn = self._setup_duckdb_connection()
            self._generate_tpch_data()

        # Generate tables in order (small to large)
        table_order = [
            ("nation", None),
            ("region", None),
            ("customer", None),
            ("supplier", None),
            ("part", None),
            ("partsupp", None),
            ("orders", None),
            ("lineitem", "l_shipdate"),  # Partitioned by shipdate
        ]

        total_tables = len(table_order)
        for idx, (table_name, partition_by) in enumerate(table_order, 1):
            logger.info(f"Processing table {idx}/{total_tables}: {table_name}")
            self.generate_table(table_name, partition_by)

        logger.info(
            f"Successfully generated all {total_tables} TPC-H tables "
            f"at scale factor {self.scale_factor}"
        )

        # Log dataset size information
        self._log_dataset_info()

    def _log_dataset_info(self) -> None:
        """Log information about the generated dataset.

        Queries DuckDB to get row counts and estimated sizes for each
        table.
        """
        logger.info("Dataset generation summary:")
        logger.info(f"  Scale Factor: {self.scale_factor}")
        logger.info(f"  S3 Location: s3://{self.s3_bucket}/{self.s3_prefix}")

        try:
            # Get row counts for each table
            for table_name in self.TPCH_TABLES:
                result = self.conn.execute(
                    f"SELECT COUNT(*) as cnt FROM {table_name}"
                ).fetchone()
                row_count = result[0] if result else 0
                logger.info(f"  {table_name}: {row_count:,} rows")

        except Exception as e:
            logger.warning(f"Could not retrieve dataset statistics: {e}")

    def close(self) -> None:
        """Close the DuckDB connection.

        Should be called when done with the generator to free resources.
        """
        if self.conn:
            logger.debug("Closing DuckDB connection")
            self.conn.close()
            self.conn = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures connection is closed."""
        self.close()
