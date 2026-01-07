# TPC-H Data Generation Module

This module contains components for generating TPC-H benchmark data at various scale factors.

## Purpose

Generate industry-standard TPC-H benchmark data and write it to S3 in Parquet format with appropriate partitioning.

## Key Components

- **TPCHGenerator**: Main class for generating TPC-H data using DuckDB
- Data generation utilities
- S3 upload functionality
- Partitioning logic for lineitem table

## Usage

```python
from src.generation.tpch_generator import TPCHGenerator

# Initialize generator
generator = TPCHGenerator(
    scale_factor=10,
    s3_bucket="my-bucket",
    s3_prefix="tpch-data"
)

# Generate all tables
generator.generate_all_tables()
```

## Requirements

See `.env.example` for required environment variables:
- `S3_BUCKET_NAME`
- `TPCH_SCALE_FACTOR`
- `AWS_REGION`
